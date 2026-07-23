# 120. PgBouncer: pool de conexiones a Postgres

## Qué cierra esto

El último punto de la categoría C de la auditoría técnica externa de julio 2026: **E-003 (PgBouncer)**. Con esto, la categoría C queda completamente cerrada — solo queda la categoría D (refactors grandes de `User` y migración a SQLAlchemy async), explícitamente diferida hasta tener evidencia real de carga.

## El problema real

Cada réplica del backend (`backend-1`, `backend-2`, ver docs/117) trae su propio pool de conexiones de SQLAlchemy (`DB_POOL_SIZE=10` + `DB_MAX_OVERFLOW=20` por defecto — `backend/app/core/config.py`). Sin un pooler intermedio, el número de conexiones **reales** a Postgres crece linealmente con el número de réplicas: 2 réplicas ya pueden abrir hasta 60 conexiones reales en pico, y `worker-bulk`/`worker-scheduler` suman más. Escalar horizontalmente más allá de 2 réplicas (algo que docs/117 dejó explícitamente fácil de hacer) puede agotar `max_connections` de Postgres (típicamente 100) mucho antes de que la base se quede sin capacidad de cómputo real.

## Diseño

**Imagen: `edoburu/pgbouncer`, no Bitnami.** La imagen `bitnami/pgbouncer` (la primera opción evaluada, con configuración 100% por variables de entorno) pasó a ser parte de "Bitnami Secure Images", de pago — ya no se puede extraer gratis de Docker Hub. `edoburu/pgbouncer` es una imagen de comunidad activamente referenciada que soporta exactamente el mismo patrón (`DATABASE_URL` + variables sueltas como `AUTH_TYPE`/`POOL_MODE`/`LISTEN_PORT` generan `pgbouncer.ini` y `userlist.txt` automáticamente al arrancar) sin depender de una oferta comercial.

**`pool_mode=transaction`, verificado seguro para este proyecto.** Es el modo más eficiente (la conexión real a Postgres se libera apenas termina cada transacción, no queda atada al ciclo de vida de la conexión del cliente), pero no soporta correctamente advisory locks, `LISTEN`/`NOTIFY` ni prepared statements de sesión. Se verificó por grep en todo `backend/app/` que este proyecto no usa ninguna de las tres cosas — el único `SELECT ... FOR UPDATE` mencionado en el código ni siquiera está implementado (comentario explícito: "no hay bloqueo de fila", limitación aceptada desde antes por compatibilidad con SQLite). Seguro de usar aquí.

**`AUTH_TYPE=scram-sha-256`**, para calzar con el método de autenticación por defecto de Postgres 16 (que no se está sobreescribiendo en el servicio `postgres` del compose). El entrypoint de la imagen genera `userlist.txt` con la contraseña real extraída de `DATABASE_URL`, usada tanto para autenticar clientes hacia PgBouncer como para que PgBouncer se autentique hacia Postgres.

**Migraciones siguen yendo directo a Postgres, nunca a través de PgBouncer.** `docs/61` ya documentaba `alembic upgrade head` como paso manual antes de levantar el stack — sin cambios ahí. DDL administrativo puntual no es el caso de uso que PgBouncer optimiza, y mezclar migraciones con el pool de transacciones de la aplicación solo agrega riesgo sin beneficio.

**Solo `backend-1`, `backend-2`, `worker-bulk`, `worker-scheduler` cambian su `DATABASE_URL`** de `postgres:5432` a `pgbouncer:6432` — el resto del compose no se toca. Sin puerto publicado al host (mismo criterio que `postgres`/`redis`/`prometheus`: solo lo consumen servicios internos de este mismo compose).

## Archivos modificados

- `docker-compose.production.example.yml`: servicio `pgbouncer` nuevo; `DATABASE_URL` de `backend-1`/`backend-2`/`worker-bulk`/`worker-scheduler` repuntado a `pgbouncer:6432`; sus `depends_on` ganan `pgbouncer` (`condition: service_started`, no tiene healthcheck propio).
- `docs/61_DESPLIEGUE_PRODUCCION_REFERENCIA.md`: sección "PgBouncer" nueva, actualizado el comando de arranque (paso 6) y la sección de PostgreSQL.
- `docs/62_CHECKLIST_GO_LIVE.md`: ítem de checklist actualizado (antes decía "evaluar PgBouncer", ahora confirma que está resuelto) + comando de logs.
- `docs/64_ROLLBACK_OPERATIVO.md`: comandos de `up`/`logs` incluyen `pgbouncer`.
- `docs/ARQUITECTURA_TECNICA_INFOMATT360.md`: diagrama Mermaid (nodo `pgbouncer` entre los servicios de aplicación y Postgres), tabla de servicios (10 → 11), tabla de imágenes, tabla de puertos, sección 8 con el diseño completo.
- `scripts/check-production-package.ps1`: checks nuevos (`pgbouncer:` como servicio, `POOL_MODE: transaction`, `DATABASE_URL` apuntando a `pgbouncer:6432`).

## Verificación real con Podman (2026-07-23)

Mismo criterio que docs/117/118/119 — no solo YAML validado, sino el pool funcionando de verdad:

- **Conexión directa a través de PgBouncer confirmada:** una conexión psycopg2 contra `pgbouncer:6432` (en vez de `postgres:5432`) ejecutó consultas reales (`SELECT version_num FROM alembic_version`, `SELECT count(*) FROM mail_profiles`) sin errores.
- **`userlist.txt` generado correctamente** por el entrypoint de la imagen a partir de `DATABASE_URL`, con las credenciales reales.
- **`backend-1`, `backend-2` y `backend-lb` sanos conectándose exclusivamente a través de PgBouncer** (`DATABASE_URL=...@pgbouncer:6432/...`), healthchecks en verde.
- **Multiplexado real confirmado con `SHOW POOLS`/`SHOW STATS` del propio PgBouncer** (consultado vía su consola de administración, `admin_users=infomatt360`): en reposo, `sv_idle: 1` (una sola conexión real a Postgres) atendiendo a los clientes de ambas réplicas. Confirmado además contando conexiones directamente en `pg_stat_activity` de Postgres: solo 2 conexiones reales visibles con ambas réplicas del backend activas.
- **Bajo carga real (k6, 20 VUs sostenidos, mismo script de docs/119):** 100% de éxito (1183/1183 checks), 0% de error. `SHOW POOLS` durante la carga mostró `cl_active: 14` (conexiones de cliente desde `backend-1`/`backend-2`) multiplexadas sobre solo `sv_idle: 4 + sv_used: 6 = 10` conexiones reales a Postgres — exactamente el comportamiento que PgBouncer promete: más clientes que conexiones reales al servidor.
- Base de datos de prueba sembrada con `seed_demo` para poder correr el load test contra datos reales.
- Stack completo desmontado al final (`podman compose down -v`), imágenes de prueba y archivos `.env`/`.env.production` temporales eliminados.

`pytest -q` completo del backend después del cambio (sin código Python modificado, solo infraestructura): sin regresiones, mismos resultados que antes.

**Límite explícito, no fingido:** esto prueba que el pool multiplexa conexiones correctamente en un solo host de desarrollo con carga moderada (20 VUs). El beneficio real de PgBouncer se demuestra a escala de producción con muchas más réplicas y conexiones simultáneas — eso solo se puede confirmar con un despliegue real en el VPS del usuario, idealmente corriendo `loadtest/k6-infomatt360.js` (docs/119) a la escala completa de 3.000 usuarios y comparando el conteo de conexiones reales en Postgres con y sin PgBouncer.

## Lo que queda fuera de esta sesión

**La categoría C de la auditoría técnica externa queda completamente cerrada** (E-001 balanceo/réplicas, E-004 cache de permisos ya cerrado antes, observabilidad, script de prueba de carga, y ahora PgBouncer). Solo queda la categoría D (descomposición de la entidad `User`, migración de SQLAlchemy síncrono a `AsyncSession`/asyncpg), explícitamente diferida hasta que el usuario corra la prueba de carga real de 3.000 usuarios (docs/119) contra un despliegue real y esa evidencia muestre que hace falta.
