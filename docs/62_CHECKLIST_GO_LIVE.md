# Checklist go-live de InfoMatt360

## Objetivo

Usar esta lista antes de abrir InfoMatt360 a usuarios reales o integraciones
externas. La idea es evitar salir a produccion con configuracion incompleta,
sin backups o sin capacidad de diagnostico.

## 1. Seguridad y secretos

- [ ] `SECRET_KEY` generado con `scripts/generate-secret.cmd`.
- [ ] `.env.production` no esta versionado ni compartido por canales inseguros.
- [ ] `ENVIRONMENT=production`.
- [ ] `DEBUG=false`.
- [ ] `AUTO_CREATE_TABLES=false`.
- [ ] `REFRESH_COOKIE_SECURE=true`.
- [ ] `REFRESH_COOKIE_SAMESITE=strict` o `lax`.
- [ ] `FRONTEND_URL` usa `https://`.
- [ ] `CORS_ALLOWED_ORIGINS` es explicito, usa `https://` y no contiene `*`.
- [ ] SMTP real configurado para recuperacion de contrasena.
- [ ] `scripts/doctor-production.cmd -EnvFile .env.production` pasa sin fallos.

## 2. Base de datos

- [ ] `DATABASE_URL` apunta a PostgreSQL, no SQLite.
- [ ] Pool configurado: `DB_POOL_SIZE`, `DB_MAX_OVERFLOW`, `DB_POOL_TIMEOUT_SECONDS`, `DB_POOL_RECYCLE_SECONDS`.
- [ ] Migraciones Alembic ejecutadas con `alembic upgrade head`.
- [ ] Backup inicial tomado antes de abrir trafico con `scripts/backup-postgres.cmd`.
- [ ] Politica de backups definida: frecuencia, retencion, responsable y ubicacion.
- [ ] Prueba de restauracion realizada en ambiente no productivo con `scripts/restore-postgres.cmd`.
- [ ] Espacio en disco monitoreado.
- [ ] PgBouncer evaluado si habra multiples replicas o alto volumen.

## 3. Redis y limites

- [ ] `REDIS_URL` configurado si se usan limites distribuidos.
- [ ] `API_RATE_LIMIT_BACKEND=redis` para despliegue multiworker.
- [ ] `AUTH_THROTTLE_BACKEND=redis` si login/MFA/refresh tendran alto volumen.
- [ ] Limites de API keys revisados para integraciones masivas.
- [ ] Perfiles de API key asignados por integracion: default, high_volume o trusted_sync.
- [ ] Redis con persistencia, memoria maxima y monitoreo.

## 4. Worker bulk

- [ ] Worker bulk separado del backend web.
- [ ] `BULK_WORKER_RETRY_BACKOFF_SECONDS` definido.
- [ ] `BULK_WORKER_RETRY_MAX_BACKOFF_SECONDS` definido.
- [ ] `BULK_WORKER_STALE_AFTER_SECONDS` definido.
- [ ] `BULK_WORKER_HEARTBEAT_EVERY_RECORDS` definido.
- [ ] Panel `/admin/bulk-jobs` revisado con permisos correctos.
- [ ] Procedimiento definido para reintentar, exportar errores CSV y revisar `last_error`.

## 5. Frontend, dominio y HTTPS

- [ ] Dominio frontend configurado.
- [ ] Dominio API configurado.
- [ ] TLS/HTTPS activo en ambos dominios.
- [ ] Certificados con renovacion automatica.
- [ ] Proxy o balanceador preserva IP real solo desde origen confiable.
- [ ] `API_RATE_LIMIT_TRUSTED_PROXY_IPS` configurado si se usa proxy.
- [ ] CSP final del frontend revisada si se sirve desde infraestructura propia.

## 6. Observabilidad

- [ ] `REQUEST_LOGGING_ENABLED=true`.
- [ ] `REQUEST_ID_HEADER=X-Request-ID`.
- [ ] `METRICS_ENABLED=true`.
- [ ] `/api/v1/health/ready` responde `ready`.
- [ ] `/api/v1/health/metrics` accesible solo con permisos operativos.
- [ ] `/api/v1/health/metrics/prometheus` conectado o listo para monitoreo externo.
- [ ] Alertas definidas para `5xx`, `429`, fallos bulk y jobs atascados.
- [ ] Logs centralizados y buscables por `X-Request-ID`.
- [ ] Monitor liviano `scripts/monitor-health.cmd` configurado o reemplazado por monitoreo externo.

## 7. Validacion funcional

- [ ] `scripts/check-health.cmd` contra URLs productivas.
- [ ] Login de usuario administrador validado.
- [ ] Recuperacion de contrasena probada con SMTP real.
- [ ] MFA probado, incluyendo codigos de recuperacion.
- [ ] Creacion/correccion de usuario desde admin probada.
- [ ] Flujo de aprobacion configurable validado.
- [ ] Captura runtime validada.
- [ ] Evidencias/archivos validados con `UPLOAD_DIRECTORY` persistente.
- [ ] Reportes XLSX/CSV validados.
- [ ] API key de integracion probada.
- [ ] Lote bulk `queued` probado con worker.

## 8. Operacion y rollback

- [ ] Responsable de soporte definido.
- [ ] Ventana de despliegue definida.
- [ ] Plan de rollback documentado segun `docs/64_ROLLBACK_OPERATIVO.md`.
- [ ] Backup de base antes del despliegue.
- [ ] Version del ZIP/commit registrada.
- [ ] SHA256 del paquete registrado.
- [ ] Procedimiento de reinicio de backend, frontend y worker documentado.
- [ ] Procedimiento para pausar integraciones externas documentado.

## Comandos utiles

```powershell
.\scripts\doctor-production.cmd -EnvFile .env.production
.\scripts\check-production-package.cmd
.\scripts\backup-postgres.cmd -EnvFile .env.production
.\scripts\monitor-health.cmd -BackendUrl https://api.tu-dominio.com -FrontendUrl https://app.tu-dominio.com -Iterations 3
.\scripts\check-health.cmd -BackendUrl https://api.tu-dominio.com -FrontendUrl https://app.tu-dominio.com
.\scripts\make-status-report.cmd
.\scripts\make-release.cmd
```

Con Docker Compose de referencia:

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production ps
docker compose -f docker-compose.production.example.yml --env-file .env.production logs backend
docker compose -f docker-compose.production.example.yml --env-file .env.production logs worker-bulk
```
