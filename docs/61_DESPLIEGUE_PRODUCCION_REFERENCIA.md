# Despliegue productivo de referencia

## Objetivo

Dejar una receta base para operar InfoMatt360 separando responsabilidades:

- API backend;
- frontend estatico;
- worker bulk independiente;
- PostgreSQL persistente;
- Redis para rate limiting y throttling distribuido;
- volumen persistente para evidencias/subidas.

## Archivos agregados

```text
docker-compose.production.example.yml
.dockerignore
deploy/backend.Dockerfile
deploy/frontend.Dockerfile
deploy/nginx.frontend.conf
deploy/nginx.backend-lb.conf
deploy/prometheus.yml
deploy/grafana/provisioning/
```

(PgBouncer, docs/120, no necesita archivo de configuracion propio -- se
configura entero por variables de entorno en `docker-compose.production.example.yml`.)

Estos archivos son una base de referencia. Antes de usarlos en produccion real
deben conectarse a dominio, TLS/HTTPS, backups, monitoreo y gestion de secretos
del proveedor de infraestructura.

## Flujo recomendado

Antes de empezar, revisar el checklist completo:

```text
docs/62_CHECKLIST_GO_LIVE.md
```

1. Crear `.env.production` a partir de `.env.production.example`.
2. Generar `SECRET_KEY` con:

```powershell
.\scripts\generate-secret.cmd
```

3. Configurar secretos reales:

```text
POSTGRES_PASSWORD
SECRET_KEY
SMTP_HOST
SMTP_USERNAME
SMTP_PASSWORD
SMTP_FROM_EMAIL
FRONTEND_URL=https://...
CORS_ALLOWED_ORIGINS=https://...
UPLOAD_DIRECTORY=/var/lib/infomatt360/uploads
```

4. Validar la configuracion:

```powershell
.\scripts\doctor-production.cmd -EnvFile .env.production
```

Validar que los artefactos productivos de referencia esten completos:

```powershell
.\scripts\check-production-package.cmd
```

5. Ejecutar migraciones Alembic antes de abrir trafico:

Antes de migrar, tomar backup:

```powershell
.\scripts\backup-postgres.cmd -EnvFile .env.production
```

```powershell
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
```

6. Levantar `postgres`, `redis`, `pgbouncer` y las replicas del backend
   primero (el stack de observabilidad necesita un token que solo se puede
   generar con el backend ya arriba):

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production up -d --build postgres redis pgbouncer backend-1 backend-2 backend-lb worker-bulk worker-scheduler frontend
```

7. Generar el token de scraping de Prometheus (docs/118) y guardarlo donde
   `docker-compose.production.example.yml` lo espera montado:

```powershell
mkdir secrets -Force
docker compose -f docker-compose.production.example.yml --env-file .env.production exec backend-1 python -m app.cli.generate_metrics_token > secrets\metrics_token
```

8. Levantar el stack de observabilidad:

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production up -d prometheus grafana
```

## Componentes

### Backend

Corre en 2 replicas (`backend-1`, `backend-2`) detras de `backend-lb`, que es
el que expone el puerto `8000` (ver "Balanceador de carga" abajo). Ninguna
replica publica puerto al host directamente. Debe quedar detras de un proxy
con HTTPS. El endpoint de readiness es:

```text
GET /api/v1/health/ready
```

### Balanceador de carga (backend-lb)

nginx (`deploy/nginx.backend-lb.conf`) balancea round-robin entre `backend-1`
y `backend-2` (ver docs/117), con `proxy_next_upstream` para saltar a la otra
replica si una falla. Tiene IP fija (`172.28.0.10`, subred `172.28.0.0/24`
declarada al final de `docker-compose.production.example.yml`) para que
`API_RATE_LIMIT_TRUSTED_PROXY_IPS` (`.env.production.example`) pueda confiar
en su `X-Forwarded-For` y el backend siga viendo la IP real del cliente para
rate limiting y throttle de login -- sin esa variable configurada, todo el
trafico se veria como si viniera de `backend-lb`.

### Worker bulk

Usa la misma imagen del backend, pero ejecuta:

```text
python -m app.cli.process_bulk_jobs --limit 50 --loop --sleep-seconds 5 --worker-id worker-bulk-01
```

Esto mantiene las cargas masivas fuera del proceso web y evita que la API se
degrade con sincronizaciones pesadas.

### Worker scheduler

Usa la misma imagen del backend, pero ejecuta:

```text
python -m app.cli.run_scheduled_tasks --limit 50 --loop --sleep-seconds 60
```

Sin este worker, las `ScheduledTask` recurrentes (respaldos automaticos,
docs/78, y el sondeo de la bandeja externa IMAP, docs/116) quedan guardadas
en la base de datos pero nunca se ejecutan.

### Frontend

Se sirve con nginx. Para produccion real, colocar un proxy/TLS delante o adaptar
la imagen para el dominio final.

### PostgreSQL

Debe tener backups, monitoreo de disco y politica de retencion. Las
migraciones (`alembic upgrade head`, paso 5 arriba) van directo a `postgres`,
nunca a traves de `pgbouncer` -- DDL y comandos administrativos no son el
caso de uso que PgBouncer optimiza, y es una operacion manual puntual, no
trafico de aplicacion en regimen.

### PgBouncer

Pool de conexiones (E-003, auditoria tecnica externa julio 2026, docs/120).
`backend-1`, `backend-2`, `worker-bulk` y `worker-scheduler` ya no se
conectan directo a `postgres:5432` -- su `DATABASE_URL` apunta a
`pgbouncer:6432`. Sin esto, el numero de conexiones reales a Postgres crece
linealmente con el numero de replicas del backend (cada una con su propio
pool de SQLAlchemy, `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`) y puede agotar
`max_connections` de Postgres mucho antes de que la base se quede sin
capacidad real -- justo el problema que aparece al escalar mas alla de las
2 replicas de E-001.

`pool_mode=transaction` (el mas eficiente: la conexion real a Postgres se
libera apenas termina cada transaccion, no se mantiene atada al ciclo de
vida de la conexion del cliente). Verificado que este proyecto no usa
advisory locks, `LISTEN`/`NOTIFY` ni prepared statements de sesion -- las
tres cosas que transaction pooling no soporta correctamente -- asi que es
seguro usarlo aqui (docs/120).

No publica puerto al host: solo lo consumen los servicios internos de este
mismo compose. Sin archivo de configuracion propio -- toda su configuracion
sale de variables de entorno (`DATABASE_URL`, `AUTH_TYPE`, `POOL_MODE`,
etc.) en `docker-compose.production.example.yml`.

### Redis

Se usa para rate limiting y throttling distribuido. Debe tener persistencia,
limites de memoria y monitoreo.

### Prometheus

Stack de observabilidad (auditoria tecnica externa julio 2026, docs/118).
Scrapea `backend-1` y `backend-2` directo cada 15s (`deploy/prometheus.yml`),
nunca a traves de `backend-lb` -- las metricas viven en memoria por proceso,
asi que scrapear a traves del balanceador daria una serie inconsistente
(cada scrape caeria en una replica distinta). No publica puerto al host: su
UI no tiene autenticacion propia, asi que exponerla directo a internet seria
un hueco de seguridad real. Se consulta a traves de Grafana o via tunel SSH
(`ssh -L 9090:localhost:9090 usuario@servidor`, luego `podman exec` o
`docker exec` para publicar el puerto del contenedor si hace falta debug
directo).

Requiere `secrets/metrics_token` (paso 7 arriba) montado como
`/run/secrets/metrics_token` -- si el archivo no existe antes del primer
`up`, Docker/Podman crean un directorio vacio en su lugar en vez de fallar,
y Prometheus arranca sin poder autenticarse. Generar el archivo siempre
antes de levantar `prometheus`.

### Grafana

Puerto `3000` publicado al host (si tiene login propio). Usuario `admin`,
contrasena en `GF_SECURITY_ADMIN_PASSWORD` (`.env.production`). Datasource
de Prometheus y un dashboard inicial ("InfoMatt360 - Vision general": estado
de las replicas, tasa de errores 5xx, requests/seg por replica, latencia
p50/p95/p99, requests por familia de status, throughput del worker bulk) se
provisionan solos desde `deploy/grafana/provisioning/` -- no hace falta
configurarlos a mano.

### Prueba de carga (loadtest/)

`loadtest/k6-infomatt360.js` (docs/119) genera la evidencia real de
capacidad que pedia la auditoria tecnica externa. A escala minima (default)
es seguro correrla contra cualquier entorno; a escala de 3.000 usuarios
(`TARGET_VUS=3000`) subir antes `API_RATE_LIMIT_REQUESTS` temporalmente --
ver `loadtest/README.md`, seccion sobre rate limiting por IP. Ver
`loadtest/README.md` para el procedimiento completo.

## Verificaciones despues de desplegar

```powershell
.\scripts\check-health.cmd -BackendUrl https://api.tu-dominio.com -FrontendUrl https://app.tu-dominio.com
```

Luego revisar:

- `/api/v1/health/ready`;
- `/api/v1/health/metrics`;
- `/admin/metrics`;
- `/admin/bulk-jobs`;
- logs por `X-Request-ID`.

## Nota de seguridad

No versionar `.env.production` ni secretos reales. El ZIP de entrega excluye
`.env`, pero los secretos productivos deben vivir en el gestor de secretos del
servidor, proveedor cloud o pipeline CI/CD.

El repositorio ignora `.env.production`, `backend/.env.production` y variantes
locales de entorno. El archivo `.dockerignore` evita enviar secretos, bases
locales, entornos virtuales, `node_modules`, builds y uploads al contexto de
construccion Docker.
