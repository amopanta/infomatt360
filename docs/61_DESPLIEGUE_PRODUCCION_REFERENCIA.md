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
```

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

6. Levantar servicios con la receta de referencia:

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production up -d --build
```

## Componentes

### Backend

Expone la API en el puerto `8000`. Debe quedar detras de un proxy con HTTPS.
El endpoint de readiness es:

```text
GET /api/v1/health/ready
```

### Worker bulk

Usa la misma imagen del backend, pero ejecuta:

```text
python -m app.cli.process_bulk_jobs --limit 50 --loop --sleep-seconds 5 --worker-id worker-bulk-01
```

Esto mantiene las cargas masivas fuera del proceso web y evita que la API se
degrade con sincronizaciones pesadas.

### Frontend

Se sirve con nginx. Para produccion real, colocar un proxy/TLS delante o adaptar
la imagen para el dominio final.

### PostgreSQL

Debe tener backups, monitoreo de disco y politica de retencion. En alto volumen,
considerar PgBouncer.

### Redis

Se usa para rate limiting y throttling distribuido. Debe tener persistencia,
limites de memoria y monitoreo.

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
