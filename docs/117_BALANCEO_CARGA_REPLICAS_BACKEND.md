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

## Corrección de un bug preexistente encontrado de paso

`scripts/check-production-package.ps1` (que valida que la receta de producción tenga todas las piezas esperadas) fallaba en sus 5 checks de `.dockerignore` **desde antes de este cambio** (confirmado con `git log`, no es una regresión de esta sesión): usaba regex `(?m)^\.env$` etc., pero `.dockerignore` tiene terminadores de línea CRLF, así que el contenido real de cada línea es `.env\r` — el `\r` sobrante hacía que el regex nunca calzara. Corregido a `(?m)^\.env\r?$` (y equivalente en los otros 4 checks). Se aprovechó para agregar los checks nuevos de esta feature (`backend-1`, `backend-2`, `backend-lb`, `worker-scheduler`, `nginx.backend-lb.conf`, contenido del upstream) al mismo script.

## Verificación

- `python -c "import yaml; yaml.safe_load(open('docker-compose.production.example.yml'))"`: YAML válido, 8 servicios, `networks`/`depends_on`/IP fija con la forma esperada.
- `.\scripts\check-production-package.ps1`: **Paquete productivo de referencia OK** (0 fallos, incluyendo los 5 checks de `.dockerignore` recién arreglados y los nuevos de esta feature).

**Límite explícito, no fingido:** no hay Docker ni un VPS real disponible en este entorno de desarrollo para levantar el stack completo y confirmar en vivo que nginx efectivamente reparte tráfico entre `backend-1`/`backend-2` y que el failover funciona si una réplica cae — mismo criterio de honestidad ya aplicado en docs/113 (Postgres/PostGIS real) y docs/114 (Tableau Desktop real). Lo verificado aquí es la validez sintáctica/estructural de toda la configuración y que la receta se auto-documenta y se auto-valida de forma coherente; la prueba real de balanceo/failover queda pendiente de un despliegue real en el VPS que decida el usuario, idealmente junto con el script de prueba de carga (aún no construido) que generaría la evidencia de 3.000 usuarios que pide la auditoría original.

## Lo que queda fuera de esta sesión

De la categoría C de la auditoría técnica externa: E-003 (PgBouncer) y el stack de observabilidad (Prometheus/Grafana sobre el endpoint de métricas ya existente) siguen sin construir. El script de prueba de carga (k6/locust) tampoco se ha escrito. La categoría D (descomposición de `User`, migración a SQLAlchemy async) sigue explícitamente diferida hasta tener evidencia real de carga.
