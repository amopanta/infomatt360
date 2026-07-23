# 117. Balanceo de carga y réplicas del backend

## Qué cierra esto

El hallazgo **E-001** de la auditoría técnica externa de julio 2026 (categoría C — "mayormente decisiones reales de infraestructura"): la receta de referencia (`docker-compose.production.example.yml`) corría el backend como un único proceso `backend`, sin réplicas ni balanceador — un punto único de falla y el techo real de throughput de toda la aplicación. Estaba explícitamente marcado como **bloqueado** en la auditoría previa (docs/108) hasta que el usuario tomara una decisión de hosting.

**Decisión de hosting (2026-07-20, confirmada por el usuario):** VPS/servidor propio con Docker Compose, no cloud gestionado. Esto habilita construir E-001 directamente en la receta de referencia existente, en vez de proponer servicios gestionados (ALB de AWS, Cloud Load Balancing de GCP, etc.) que no aplican a ese escenario.

## Diseño

**2 réplicas explícitas (`backend-1`, `backend-2`), no `deploy.replicas`.** Docker Compose sin Swarm no hace balanceo real entre réplicas de un mismo `deploy.replicas` — `docker compose up --scale` funciona pero requiere quitar el mapeo de puerto al host (conflicto de puertos) y depender del DNS embebido de Docker para el round-robin, lo cual es frágil de razonar y de documentar en una receta de referencia. Definir `backend-1`/`backend-2` como servicios explícitos (mismo patrón ya usado en este archivo para `worker-bulk`/`worker-scheduler`: bloques casi idénticos, imagen compartida) es más predecible: el `upstream` de nginx los nombra por su DNS de servicio de Compose, sin depender de resolución dinámica.

**`backend-lb` (nginx) como balanceador, no como parte de `frontend`.** El `frontend` nginx ya existente sirve la SPA estática en el puerto 8080; mezclar balanceo de API ahí habría acoplado dos responsabilidades distintas. `backend-lb` es un servicio nuevo, solo nginx (`deploy/nginx.backend-lb.conf`, sin build propio, mismo criterio que ya usa `frontend` para no necesitar login/lógica propia), que:
- Publica el puerto `8000` al host — el mismo que antes usaba `backend` directamente. Ningún cliente externo (SPA, Electron, integraciones) necesita cambiar de URL.
- Reparte round-robin entre `backend-1:8000` y `backend-2:8000` vía un bloque `upstream`.
- Usa `proxy_next_upstream error timeout http_502 http_503 http_504` para saltar a la otra réplica si una falla — el punto real de tener 2 réplicas es tolerar la caída de una.

**IP fija para `backend-lb`, no dejarla a la resolución dinámica de Docker.** El repo ya tenía un mecanismo real para esto (`API_RATE_LIMIT_TRUSTED_PROXY_IPS`, usado por `app/middleware/rate_limit.py` para decidir si confiar en `X-Forwarded-For`; `app/api/v1/health.py` ya advertía en producción si esta variable no estaba configurada). Sin una IP predecible para el proxy, `backend-1`/`backend-2` verían todo el tráfico como si viniera de `backend-lb`, rompiendo el rate limiting y el throttle de login por IP real. Se declaró una subred fija `172.28.0.0/24` en el bloque `networks` del compose y se le asignó `172.28.0.10` a `backend-lb`; `.env.production.example` quedó con `API_RATE_LIMIT_TRUSTED_PROXY_IPS=172.28.0.10` apuntando a esa IP.

**Migraciones siguen corriendo una sola vez, fuera de Compose.** `docs/61` ya documentaba correr `alembic upgrade head` como paso manual antes de `docker compose up`, y `AUTO_CREATE_TABLES=false` en todos los servicios — con 2 réplicas del backend esto sigue siendo correcto sin cambios: ninguna réplica intenta crear/migrar el esquema al arrancar.

## Archivos modificados

- `docker-compose.production.example.yml`: `backend` → `backend-1` + `backend-2` (sin puerto al host) + `backend-lb` (nuevo, puerto `8000:80`, IP fija); `frontend.depends_on` apunta a `backend-lb`; nuevo bloque `networks` con subred `172.28.0.0/24`.
- `deploy/nginx.backend-lb.conf` (nuevo): `upstream` con las 2 réplicas, `X-Forwarded-For`/`X-Real-IP`, `proxy_next_upstream`.
- `.env.production.example`: `API_RATE_LIMIT_TRUSTED_PROXY_IPS` actualizado a la IP fija real de `backend-lb`.
- `docs/61_DESPLIEGUE_PRODUCCION_REFERENCIA.md`: sección "Balanceador de carga (backend-lb)" nueva, sección "Backend" actualizada.
- `docs/62_CHECKLIST_GO_LIVE.md`: ítem de checklist + comandos de logs para `backend-1`/`backend-2`/`backend-lb`.
- `docs/64_ROLLBACK_OPERATIVO.md`: comandos de `up`/`logs` actualizados a los 3 servicios.
- `docs/ARQUITECTURA_TECNICA_INFOMATT360.md`: diagrama Mermaid (nodo `backend-lb`, subgraph backend marcado "x2 réplicas"), tabla de servicios (6 → 8 filas), tablas de imágenes/puertos, variable `API_RATE_LIMIT_TRUSTED_PROXY_IPS` con valor real, sección 8 ya no marca "Pendiente de confirmar por infraestructura" para escalado horizontal/balanceador (sí sigue pendiente la evidencia de carga real que justifique más de 2 réplicas).
- `backend/alembic/env.py` (hallazgo crítico, ver abajo): ensancha `alembic_version.version_num` en Postgres antes de migrar.
- `.gitattributes` (nuevo, hallazgo secundario, ver abajo): fuerza LF en `.dockerignore`.

## Corrección de un bug preexistente encontrado de paso

`scripts/check-production-package.ps1` (que valida que la receta de producción tenga todas las piezas esperadas) fallaba en sus 5 checks de `.dockerignore` **desde antes de este cambio** (confirmado con `git log`, no es una regresión de esta sesión): usaba regex `(?m)^\.env$` etc., pero `.dockerignore` tiene terminadores de línea CRLF, así que el contenido real de cada línea es `.env\r` — el `\r` sobrante hacía que el regex nunca calzara. Corregido a `(?m)^\.env\r?$` (y equivalente en los otros 4 checks). Se aprovechó para agregar los checks nuevos de esta feature (`backend-1`, `backend-2`, `backend-lb`, `worker-scheduler`, `nginx.backend-lb.conf`, contenido del upstream) al mismo script.

## Verificación

- `python -c "import yaml; yaml.safe_load(open('docker-compose.production.example.yml'))"`: YAML válido, 8 servicios, `networks`/`depends_on`/IP fija con la forma esperada.
- `.\scripts\check-production-package.ps1`: **Paquete productivo de referencia OK** (0 fallos, incluyendo los 5 checks de `.dockerignore` recién arreglados y los nuevos de esta feature).

### Prueba real con Podman (2026-07-23)

A diferencia de items anteriores de esta sesión donde no había forma de probar en vivo, esta vez sí: Podman (con su VM WSL2) ya estaba instalado en esta máquina. Se levantó la receta completa (`docker-compose.production.example.yml`, imagen `postgres` sustituida por `postgis/postgis:16-3.4` solo para esta prueba porque la imagen `postgres:16` de la receta no trae PostGIS — limitación ya documentada en el propio archivo) contra una base Postgres real, desde cero:

- **Round-robin real confirmado:** 20 requests externas consecutivas a `http://localhost:8000/api/v1/health/ready` (el puerto publicado por `backend-lb`) se repartieron **10/10** entre `backend-1` y `backend-2`, verificado contando líneas de log de cada réplica antes/después.
- **Failover real confirmado:** con `backend-1` detenido (`podman stop`), 8 requests consecutivas a través de `backend-lb` siguieron devolviendo `200 OK` sin ninguna falla visible al cliente. El log de `backend-lb` muestra exactamente el mecanismo esperado: `upstream timed out ... while connecting to upstream ... 172.28.0.175:8000` (backend-1) seguido de `upstream server temporarily disabled` (respetando `max_fails=3 fail_timeout=10s`) y el reintento automático contra `backend-2` vía `proxy_next_upstream`.
- **Nota operativa real, no un defecto:** el primer request tras la caída de una réplica tarda hasta `proxy_connect_timeout` (10s configurados) en fallar antes de reintentar contra la réplica sana; los siguientes son inmediatos mientras el servidor caído sigue "temporarily disabled". Si se quiere un failover más rápido para el primer request post-caída, se puede bajar `proxy_connect_timeout` en `deploy/nginx.backend-lb.conf` (ej. a 3s) — no se cambió en este commit porque 10s es razonable para una LAN/VPS real y no hay evidencia de que sea un problema.
- `worker-scheduler` y `worker-bulk` corriendo contra la misma base real: ambos loopean limpio (`{"processed":0,"succeeded":0,"failed":0}` / equivalente) sin errores de conexión a Postgres/Redis.
- `frontend` sirve `200 OK` en el puerto 8080.
- Migraciones (`alembic upgrade head`) corridas contra Postgres real desde una base vacía llegaron a `0069_external_mail_messages` (head) sin intervención manual — ver hallazgo crítico abajo, que solo se descubrió gracias a esta prueba.

Stack completo desmontado al final (`podman compose down -v`, imágenes de prueba eliminadas, archivos `.env`/`.env.production` temporales borrados) — no queda nada residual en el repo ni en Podman.

**Límite que sigue siendo real:** esto prueba el balanceo/failover en un solo host (la VM de Podman), no latencia de red real entre nodos ni el comportamiento bajo carga real (eso sigue pendiente del script k6/locust, aún no construido, y de un despliegue real en el VPS). Tampoco se probó Docker en Linux directamente (el target real de producción) — solo Podman en Windows, que es compatible con el mismo `docker-compose.production.example.yml` pero no es exactamente el mismo motor.

## Hallazgo crítico encontrado durante esta prueba: `alembic_version` truncaba en Postgres real

Al correr `alembic upgrade head` contra Postgres real por primera vez en la historia de este proyecto (todo el desarrollo/demo se había corrido siempre contra SQLite), la migración **falló** con `psycopg2.errors.StringDataRightTruncation: value too long for type character varying(32)` al llegar a `0035_assignment_composite_indexes`. Alembic crea la tabla `alembic_version` con `version_num VARCHAR(32)` por defecto, pero 4 revisiones de este repo superan los 32 caracteres:

| Revisión | Caracteres |
|---|---|
| `0055_device_asset_lock_and_field_tokens` | 39 |
| `0061_runtime_record_participant_link` | 36 |
| `0062_user_organization_assignments` | 34 |
| `0035_assignment_composite_indexes` | 33 |
| `0054_governance_support_emergency` | 33 |

SQLite no aplica límites de longitud de `VARCHAR`, por eso esto nunca se notó: **el procedimiento de despliegue documentado en docs/61 (`alembic upgrade head` contra Postgres real) estaba roto desde que se creó la migración 0035**, sin que ninguna prueba lo hubiera detectado — este es exactamente el tipo de gap que solo una prueba real contra el motor de base de datos correcto puede encontrar.

**Corrección:** `backend/alembic/env.py` gana `_ensure_wide_version_table()`, llamada solo cuando `connection.dialect.name == "postgresql"`, que crea (si no existe) o ensancha la columna `alembic_version.version_num` a `VARCHAR(255)` antes de que Alembic corra ninguna migración. Se probó de extremo a extremo: con el fix aplicado, `alembic upgrade head` contra la misma base Postgres vacía llegó limpio hasta `0069_external_mail_messages`, incluyendo la creación real de la extensión PostGIS (migración 0068). `pytest -q` completo del backend después del cambio: 420 passed, mismos 5 errores preexistentes no relacionados (bloqueo de directorio de Windows).

## Hallazgo secundario: `.dockerignore` con CRLF rompe builds reales de Docker/Podman

Al intentar el primer build con Podman, `.pytest_cache` (bloqueado en este entorno Windows, ver memoria del proyecto) hizo fallar `COPY backend /app` porque **`.dockerignore` no estaba excluyendo nada realmente**: el archivo está commiteado con LF (confirmado con `git show HEAD:.dockerignore`), pero `core.autocrlf=true` (config de Git común en Windows) lo convierte a CRLF al hacer checkout, y buildah/Docker interpretan cada patrón de exclusión como coincidencia exacta de línea — con el `\r` de sobra, `.pytest_cache\r` nunca calza con el directorio real `.pytest_cache`. Cualquier desarrollador Windows con la configuración de Git por defecto que intente `docker build`/`podman build` localmente puede pisar el mismo problema. Corregido de forma permanente con un `.gitattributes` nuevo (`​.dockerignore text eol=lf`), que fuerza LF en el checkout sin importar `core.autocrlf` del usuario. (El mismo síntoma, con causa raíz idéntica, ya se había visto y parcheado de forma más limitada en `scripts/check-production-package.ps1` al cerrar este mismo ítem — esta es la corrección de raíz.)

## Lo que queda fuera de esta sesión

De la categoría C de la auditoría técnica externa: E-003 (PgBouncer) y el stack de observabilidad (Prometheus/Grafana sobre el endpoint de métricas ya existente) siguen sin construir. El script de prueba de carga (k6/locust) tampoco se ha escrito. La categoría D (descomposición de `User`, migración a SQLAlchemy async) sigue explícitamente diferida hasta tener evidencia real de carga.
