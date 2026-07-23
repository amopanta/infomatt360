# Rollback operativo

## Objetivo

Definir una ruta clara para volver a un estado estable si una salida a
produccion falla, degrada el servicio o rompe integraciones.

## Principio

Un rollback seguro requiere tres evidencias antes del despliegue:

- ZIP o imagen anterior identificada.
- SHA256 o commit/version anterior registrado.
- Backup PostgreSQL tomado antes del cambio.

Sin esos tres elementos, el rollback se convierte en recuperacion de incidente
y debe tratarse como emergencia.

## Antes del despliegue

1. Registrar paquete actual:

```text
infomatt360-mvp-source-YYYYMMDD-HHMMSS.zip
SHA256=...
```

2. Tomar backup:

```powershell
.\scripts\backup-postgres.cmd -EnvFile .env.production
```

3. Confirmar salud actual:

```powershell
.\scripts\check-health.cmd -BackendUrl https://api.tu-dominio.com -FrontendUrl https://app.tu-dominio.com
```

4. Pausar o reducir integraciones externas si el cambio afecta API bulk,
autenticacion, permisos, migraciones o estructura de datos.

## Si falla el despliegue sin migracion destructiva

1. Volver a la imagen/paquete anterior.
2. Reiniciar servicios:

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production up -d --build pgbouncer backend-1 backend-2 backend-lb frontend worker-bulk worker-scheduler
```

3. Validar:

```powershell
.\scripts\check-health.cmd -BackendUrl https://api.tu-dominio.com -FrontendUrl https://app.tu-dominio.com
```

4. Revisar logs:

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production logs pgbouncer
docker compose -f docker-compose.production.example.yml --env-file .env.production logs backend-1
docker compose -f docker-compose.production.example.yml --env-file .env.production logs backend-2
docker compose -f docker-compose.production.example.yml --env-file .env.production logs backend-lb
docker compose -f docker-compose.production.example.yml --env-file .env.production logs worker-bulk
docker compose -f docker-compose.production.example.yml --env-file .env.production logs worker-scheduler
docker compose -f docker-compose.production.example.yml --env-file .env.production logs prometheus
```

`prometheus`/`grafana` (docs/118) no se reconstruyen en un rollback -- usan
imagenes fijas, no build desde el repo, y no guardan estado de la
aplicacion que dependa de la version del codigo.

## Si falla despues de migraciones de base de datos

No asumir que basta con volver el codigo. Primero decidir si la migracion es
reversible.

Ruta segura:

1. Detener trafico o poner mantenimiento.
2. Detener worker bulk para evitar escrituras nuevas.
3. Restaurar backup en una base temporal.
4. Validar integridad funcional en esa base temporal.
5. Si el responsable aprueba, restaurar en la base objetivo:

```powershell
.\scripts\restore-postgres.cmd `
  -BackupFile .\backups\archivo.dump `
  -TargetDatabaseUrl "postgresql+psycopg2://usuario:clave@host:5432/infomatt360" `
  -ConfirmRestore RESTORE
```

6. Levantar servicios con la version anterior.
7. Ejecutar `check-health`.
8. Revisar `/admin/metrics` y `/admin/bulk-jobs`.

## Integraciones externas

Si hay sincronizaciones cada pocas horas o con millones de registros:

- pausar integraciones antes de restaurar base;
- comunicar ventana de congelamiento;
- registrar ultimo `X-Request-ID` procesado correctamente;
- al volver, reanudar desde el ultimo lote confirmado;
- revisar jobs `queued`, `processing`, `failed` y reintentos pendientes.

## Criterios para declarar rollback exitoso

- `/api/v1/health/ready` responde `ready`.
- Login administrador funciona.
- Worker bulk sin jobs atascados nuevos.
- No hay incremento sostenido de `5xx`.
- Integracion API key de prueba responde.
- Reportes/mapas/registros principales abren correctamente.
- El responsable operativo aprueba reapertura de trafico.

## Registro post-rollback

Documentar:

- fecha y hora;
- version fallida;
- version restaurada;
- backup usado;
- causa probable;
- acciones correctivas;
- si hubo perdida o reproceso de datos;
- enlaces a logs por `X-Request-ID`.
