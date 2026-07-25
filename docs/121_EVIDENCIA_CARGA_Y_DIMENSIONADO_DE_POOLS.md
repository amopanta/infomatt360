# 121. Evidencia de carga real y dimensionado de pools

## Qué es esto

La primera corrida real del script k6 de [docs/119](119_SCRIPT_PRUEBA_CARGA_K6.md) contra el stack completo de referencia. Hasta acá el script existía y estaba probado a escala chica, pero nunca se había usado para lo que fue construido: encontrar el límite real y decir *por qué*.

Encontró un cuello concreto y accionable en la configuración del paquete productivo, y lo cerró. **Ninguna línea de código de la aplicación cambió** — solo dimensionado.

## El hallazgo

Los valores de pool que traía el paquete productivo estaban por debajo del techo de concurrencia del propio backend, así que la base de datos se agotaba antes de que el backend siquiera saturara sus hilos.

**244 de los 247 endpoints de `backend/app/api/v1/` son síncronos** (`def`, no `async def`). FastAPI los corre en el threadpool de Starlette, limitado por defecto a **40 hilos por proceso**. Cada request sincrónico ocupa un hilo *y* una conexión de base de datos durante toda su vida.

Con `DB_POOL_SIZE=10` + `DB_MAX_OVERFLOW=20`, cada réplica topaba en 30 conexiones — **menos que sus propios 40 hilos**. El resultado bajo carga:

```
sqlalchemy.exc.TimeoutError: QueuePool limit of size 10 overflow 20 reached,
connection timed out, timeout 30.00
```

En paralelo, PgBouncer con `DEFAULT_POOL_SIZE=20` quedaba más ajustado que las conexiones que sus propios clientes podían pedirle. En vez de multiplexar, movía la cola: `cl_waiting: 42`, `sv_idle: 0`, `maxwait: 6s`. Los dos límites se componían.

## Medición

Stack completo de referencia (11 servicios) levantado con Podman, k6 corriendo como contenedor en la misma red contra `backend-lb`. Escenario de solo lectura (`/health/ready` + búsqueda paginada de registros), rampa 30s + 60s sostenidos.

### Curva con la configuración anterior

| VUs | Requests | Throughput | p95 búsqueda | Errores |
|---|---|---|---|---|
| 50 | 8 749 | 72 req/s | 38 ms | 0,00% |
| 100 | 16 075 | 133 req/s | 209 ms | 0,00% |
| 200 | 5 670 | **38 req/s** | 630 ms | **16,36%** |

A 200 VUs el throughput **cae a menos de un tercio** del de 100 VUs. Eso no es degradación gradual, es colapso: la cola se llena, los requests hacen timeout a los 30s, y nginx registra 144 `502` y 190 `499`.

### Mismo escenario, pools dimensionados

| 200 VUs | Antes | Después |
|---|---|---|
| Errores | 16,36% | **0,00%** |
| Requests completados | 5 670 | **22 545** |
| Throughput | 38 req/s | **186 req/s** |
| `QueuePool timeout` | crash | 0 |
| `502` / `499` en nginx | 144 / 190 | 0 / 0 |
| `cl_waiting` en PgBouncer | 42 | 0 |
| `maxwait` en PgBouncer | 6 s | 0 s |
| Contenedores | `unhealthy` 80 s | siempre `healthy` |

**5× más throughput y cero errores en 22 545 requests**, solo cambiando configuración.

La latencia a 200 VUs sí sube (p95 782 ms, por encima del umbral de 500 ms que define el script). Eso es degradación honesta bajo carga, no falla — el sistema atiende todo, más lento. El umbral del script sigue siendo el correcto para una prueba de aceptación; simplemente 200 VUs está por encima de lo que este entorno de prueba sostiene con holgura.

### Dónde está el techo: 300 VUs

Con los pools ya dimensionados, se corrió una vez más a 300 VUs para encontrar el límite:

| VUs | Requests | Throughput | p95 búsqueda | Errores |
|---|---|---|---|---|
| 50 | 8 749 | 72 req/s | 38 ms | 0,00% |
| 100 | 16 075 | 133 req/s | 209 ms | 0,00% |
| 200 | 22 545 | **186 req/s** | 782 ms | 0,00% |
| 300 | 20 487 | **169 req/s** | **1,89 s** | 0,00% |

**De 200 a 300 VUs el throughput no sube — baja levemente — mientras la latencia se multiplica por 2,4.** Ese es el techo. El sistema ya está saturado alrededor de 200 VUs y los 100 usuarios adicionales solo agregan tiempo de cola, no trabajo útil.

Es la Ley de Little en vivo: con capacidad de servicio fija, sumar concurrencia solo suma espera. Coincide con lo que predice el techo de 40 hilos × 2 réplicas.

**Lo importante es *cómo* satura.** A 300 VUs, con la configuración corregida:

- 0 errores en 20 487 requests
- 0 respuestas `502`/`499` en nginx
- 0 `QueuePool timeout`
- PgBouncer con `cl_waiting: 0` y `maxwait: 0s`
- Los contenedores **nunca** pasaron a `unhealthy`
- Reparto entre réplicas: 10 267 vs 10 266 (un request de diferencia)

Contraste directo con la configuración anterior, donde 200 VUs ya producía colapso, `502` y 80 segundos de `unhealthy`. Pasado el punto de saturación, el sistema ahora **encola y se pone lento en vez de romperse** — que es exactamente el comportamiento que se quiere.

### "Aguanta" no es lo mismo que "sirve"

A 300 VUs hay 0% de error, pero **p95 de 1,89 s es una mala experiencia de usuario**. Cero errores no significa utilizable.

La capacidad *útil* de esta configuración en este entorno está cerca de los **200 VUs** (throughput máximo, p95 782 ms). Si el objetivo es p95 < 500 ms —el umbral que define el propio script— el techo real está entre 100 y 200 VUs. Al dimensionar la infraestructura real, la métrica a mirar es el punto donde la latencia todavía es aceptable, no el punto donde empiezan los errores: están bastante separados.

## Qué se cambió

- `.env.production.example`: `DB_POOL_SIZE` 10 → **40**, `DB_MAX_OVERFLOW` 20 → **40**. El 40 no es arbitrario: iguala el techo de 40 hilos del threadpool, de modo que el pool deja de ser el límite. El overflow da margen para picos.
- `docker-compose.production.example.yml`: `DEFAULT_POOL_SIZE` de PgBouncer 20 → **60**. Holgado sobre la concurrencia real (40 hilos × 2 réplicas) y por debajo del `max_connections` de Postgres (100 por defecto).

**No se cambió el default del código** (`backend/app/core/config.py`, 10/20). Es razonable para una instancia única de desarrollo o para la suite de pruebas; la evidencia acá aplica a la topología productiva de 2 réplicas detrás de un balanceador.

## Cómo reproducirlo

Ver `loadtest/README.md`. El paso que no se puede saltear: subir `API_RATE_LIMIT_REQUESTS` temporalmente durante la ventana de prueba (todos los VUs comparten una sola IP y el límite anti-abuso de 120/60s corta la prueba con `429` sin decir nada sobre la capacidad real), y **revertirlo después**.

## Límite explícito, no fingido

Esto se midió en una VM de Podman con 2 GiB de RAM, con el generador de carga compitiendo por los mismos CPUs que los 11 contenedores. **Los números absolutos no son trasladables a un VPS real** — 186 req/s no es "la capacidad de InfoMatt360".

Lo que sí es trasladable son tres cosas, ninguna dependiente del hardware:

1. **Dónde está el cuello:** en los pools, no en CPU ni en la base.
2. **Cómo se dimensionan:** a partir del techo de 40 hilos del threadpool, que es una propiedad del código (endpoints síncronos), no de la máquina.
3. **La forma de la curva:** throughput que crece, hace plateau y luego cae levemente mientras la latencia sube en forma lineal. Ese plateau marca el punto de saturación en cualquier hardware; lo que cambia con un VPS más grande es *en qué número de usuarios* ocurre, no que ocurra.

Y una lección de método que sí aplica a la prueba real: **el punto donde la latencia deja de ser aceptable llega bastante antes que el punto donde aparecen errores**. A 300 VUs este stack da 0% de error con p95 de 1,89 s. Dimensionar mirando la tasa de error habría dado una respuesta cómoda y equivocada.

**Esto no cierra la prueba de 3.000 usuarios que pide la auditoría técnica externa** — eso sigue requiriendo un despliegue real en VPS. Pero cambia qué mirar primero cuando ese despliegue exista: estos dos parámetros, antes que cualquier refactor grande.

## Relación con la Categoría D de la auditoría

La auditoría técnica externa propone en su Categoría D migrar los 57 servicios de SQLAlchemy síncrono a `AsyncSession`/asyncpg, y esa propuesta apunta exactamente a la raíz de lo que se midió acá: con endpoints síncronos, cada request ocupa un hilo y una conexión durante toda su vida, y el techo de 40 hilos es duro.

Pero este resultado también muestra que **ese refactor no es lo primero**: el mismo cuello se corrió 5× con dos cambios de configuración y cero riesgo. La Categoría D sigue diferida hasta que exista evidencia, en un VPS real y con los pools ya bien dimensionados, de que el techo de hilos vuelve a ser el límite. Ver [[project_external_technical_audit_july_2026]].
