# Prueba de carga de InfoMatt360 (k6)

Genera la evidencia real de capacidad que pedía la auditoría técnica externa
de julio 2026 ("madurez técnica 72/100, no certificada para 3.000 usuarios
concurrentes / 300.000 requests simultáneos" — ver `docs/108`). Hasta este
ítem no existía ningún script de carga en el repositorio.

## Requisitos

- [k6](https://k6.io/) instalado, o correrlo vía contenedor:

```powershell
podman run --rm -i --network host grafana/k6 run -e BASE_URL=http://localhost:8000 - < loadtest\k6-infomatt360.js
```

(`--network host` no existe en Podman Machine para Windows/Mac — en ese caso
conectar el contenedor de k6 a la misma red de Compose y usar el nombre de
servicio, ej. `BASE_URL=http://backend-lb:80`, en vez de `localhost`.)

- Un entorno real desplegado (VPS con la receta de `docker-compose.production.example.yml`, ver `docs/61`) o, para probar que el script en sí funciona, el mismo stack levantado localmente con Podman (ver `docs/117`/`docs/118` para el procedimiento).

## Uso básico (escala mínima, seguro de correr siempre)

```powershell
k6 run loadtest\k6-infomatt360.js
```

Por defecto: 5 VUs, ~90s totales, solo lectura (`GET /api/v1/health/ready` +
`GET /api/v1/runtime/template/{id}/records/search`), contra
`http://localhost:8000` con las credenciales demo. No escribe nada.

## Generar la evidencia real de 3.000 usuarios

Antes de correrla a esa escala, leer la sección "El rate limiting por IP va
a limitar la prueba si no se ajusta antes" más abajo — con la configuración
por defecto, el propio backend va a cortar la prueba con `429` mucho antes
de llegar a 3.000 usuarios, sin que eso signifique nada sobre la capacidad
real de la aplicación.

```powershell
k6 run `
  -e BASE_URL=https://api.tu-dominio.com `
  -e LOGIN_EMAIL=usuario-de-carga@tu-org.com `
  -e LOGIN_PASSWORD=... `
  -e PROJECT_ID=<id-real> `
  -e TEMPLATE_ID=<id-real> `
  -e TARGET_VUS=3000 `
  -e RAMP_DURATION=2m `
  -e SUSTAIN_DURATION=10m `
  loadtest\k6-infomatt360.js
```

k6 reporta al final `http_req_duration` (p50/p95/p99), `http_req_failed`
(tasa de error) y el total de requests — esa salida, guardada, **es** la
evidencia de carga que pedía la auditoría. Los thresholds definidos en el
script (`p(95)<500ms` en búsquedas, `<1%` de error) hacen que k6 termine con
código de salida distinto de cero si no se cumplen, para poder engancharlo
a un pipeline si hace falta.

Si el stack tiene el stack de observabilidad de `docs/118` desplegado,
correr la prueba mientras se mira el dashboard de Grafana ("InfoMatt360 -
Visión general") en vivo es la forma más directa de ver el efecto real de
la carga sobre latencia/errores por réplica.

## Variables de entorno

| Variable | Default | Qué hace |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | URL del backend (o de `backend-lb`) |
| `LOGIN_EMAIL` / `LOGIN_PASSWORD` | credenciales demo | Cuenta usada para autenticar una sola vez en `setup()` |
| `PROJECT_ID` / `TEMPLATE_ID` | proyecto/plantilla demo | Contra qué proyecto/plantilla correr las búsquedas y (si están activadas) las escrituras |
| `TARGET_VUS` | `5` | Usuarios virtuales concurrentes del escenario de lectura |
| `WRITE_TARGET_VUS` | `TARGET_VUS / 5` | Usuarios virtuales del escenario de escritura (si está activado) |
| `RAMP_DURATION` | `30s` | Duración de la rampa de subida/bajada |
| `SUSTAIN_DURATION` | `30s` | Duración sostenida en el pico de VUs |
| `ENABLE_WRITES` | `false` | Activa el escenario de escritura (`POST /api/v1/runtime/save`) |

## Advertencia sobre el escenario de escritura

`ENABLE_WRITES=true` crea registros Runtime reales contra `PROJECT_ID`/
`TEMPLATE_ID`. Cada registro queda marcado de forma identificable
(`nombre` y `observaciones` contienen el texto `k6-load-test`) para poder
ubicarlos y borrarlos después — nunca se disfrazan de datos reales. **No
correr `ENABLE_WRITES=true` contra un proyecto de producción real sin
avisar al responsable del proyecto y tener un plan de limpieza.** Para
generar evidencia de escritura bajo carga, usar un proyecto/plantilla de
prueba dedicado, nunca datos operativos reales.

## Por qué el login se hace una sola vez, no en cada iteración

El endpoint de login tiene throttling real (`app/api/v1/auth.py`): 5
intentos fallidos por email+IP y 25 por IP cada 15 minutos antes de
bloquear. Simular 3.000 logins/segundo no reflejaría un uso real de la
aplicación (los usuarios inician sesión una vez y trabajan varias horas con
el mismo token) y además dispararía ese throttle casi de inmediato,
invalidando la prueba. El script autentica una sola vez en `setup()` y
reparte el mismo token entre todos los VUs, igual que pasaría en producción
real con miles de sesiones activas simultáneas.

## El rate limiting por IP va a limitar la prueba si no se ajusta antes

`API_RATE_LIMIT_REQUESTS`/`API_RATE_LIMIT_WINDOW_SECONDS` (`.env.production`,
default `120` requests cada `60s`) se aplican por IP de origen. k6 corriendo
desde una sola máquina hace que **todos los VUs compartan una única IP** tal
como la ve el backend — verificado en vivo (docs/119): con el límite por
defecto, una prueba sostenida de solo 5 VUs ya generaba ~20% de `429 Too
Many Requests`, no por falta de capacidad real sino por el límite de abuso
por IP haciendo exactamente su trabajo. Esto **no es un bug**, es el mismo
límite que protegería a la aplicación real de un solo cliente malicioso —
pero para generar evidencia de carga creíble hay que subirlo temporalmente
antes de correr la prueba grande:

```text
# .env.production, solo durante la ventana de la prueba de carga:
API_RATE_LIMIT_REQUESTS=1000000
```

Reiniciar `backend-1`/`backend-2` para que tomen el valor nuevo, correr la
prueba, y **revertir el valor real después** — no dejarlo así en producción
real. Si el generador de carga corre desde múltiples IPs reales (k6 Cloud,
varios agentes distribuidos), este ajuste puede no ser necesario.

## Límite honesto

Este script se probó de punta a punta a escala pequeña (decenas de VUs)
contra el stack completo levantado con Podman — ver `docs/119` — pero
**generar la evidencia real de 3.000 usuarios / 300.000 requests requiere
un despliegue real en el VPS que decida el usuario**: una máquina de
desarrollo con un solo backend Podman en modo VM no es representativa de
la capacidad de una VPS real, y ejecutar una carga de esa magnitud aquí no
produciría un número creíble. Este script es la herramienta lista para esa
prueba real, no la prueba en sí.
