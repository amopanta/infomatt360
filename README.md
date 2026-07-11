# InfoMatt360

Plataforma operativa para unificar procesos de proyectos: formularios dinamicos,
captura en campo, registros, evidencias, reportes, mapas, flujos de aprobacion,
mensajeria, API keys, sincronizacion masiva y seguridad de usuarios.

## Estado actual

MVP funcional reforzado, con backend, frontend, datos demo, pruebas
automatizadas, smoke full-stack y paquete ZIP de entrega.

Incluye:

- autenticacion con refresh token en cookie, recuperacion de contrasena y MFA TOTP;
- administracion de usuarios: corregir correo, reiniciar contrasena, reiniciar MFA y forzar cambio;
- constructor de formularios y runtime de captura;
- registros, evidencias, reportes XLSX, mapas y auditoria;
- flujos de aprobacion configurables desde panel admin;
- API keys con perfiles de rate limit;
- sincronizacion bulk para cargas masivas con worker separado, backoff y heartbeat;
- metricas operativas con p50/p95/p99, Prometheus y panel `/admin/metrics`;
- panel `/admin/bulk-jobs` para seguimiento de lotes, workers, reintentos y posibles atascos;
- permisos por proyecto y menu/rutas admin filtradas en frontend;
- health/readiness, scripts de demo, preflight, reporte y release;
- referencia de despliegue productivo con PostgreSQL, Redis, backend, frontend y worker bulk.

## Arranque rapido en Windows

Desde la raiz del proyecto:

```powershell
.\scripts\init-local.cmd
.\scripts\install-frontend.cmd
.\scripts\prepare-demo.cmd
```

Levantar backend:

```powershell
.\scripts\dev-backend.cmd
```

En otra terminal, levantar frontend:

```powershell
.\scripts\dev-frontend.cmd
```

## URLs locales

- Backend: `http://127.0.0.1:8000`
- API Docs: `http://127.0.0.1:8000/docs`
- Frontend: `http://127.0.0.1:5173`

## Credenciales demo

- Usuario: `admin@infomatt360.demo`
- Clave: `Demo12345!`
- Proyecto: `demo-project-infomatt360`

El rol demo tiene permisos amplios para validar usuarios, builder, registros,
aprobacion, API keys, sincronizacion, metricas, reportes, mapas, mensajes y
auditoria.

## Validaciones principales

Diagnostico de entorno:

```powershell
.\scripts\doctor.cmd
```

Verificar base demo:

```powershell
.\scripts\check-demo-db.cmd
```

Validar demo con backend encendido:

```powershell
.\scripts\check-demo.cmd
```

Validacion full-stack temporal:

```powershell
.\scripts\check-full-stack.cmd
```

Validar CORS local de navegador:

```powershell
.\scripts\check-browser-cors.cmd
```

Guia de revision funcional local:

```text
docs\67_REVISION_FUNCIONAL_LOCAL.md
```

Plan piloto UAT:

```text
docs\68_PLAN_PILOTO_UAT.md
```

Plantilla de evidencia UAT:

```text
docs\69_PLANTILLA_EVIDENCIA_UAT.md
```

Guia de ejecucion UAT por modulos:

```text
docs\70_GUIA_EJECUCION_UAT_MODULOS.md
```

Validar paquete productivo de referencia:

```powershell
.\scripts\check-production-package.cmd
```

Backup PostgreSQL productivo:

```powershell
.\scripts\backup-postgres.cmd -EnvFile .env.production
```

Monitor liviano de salud:

```powershell
.\scripts\monitor-health.cmd -BackendUrl https://api.tu-dominio.com -FrontendUrl https://app.tu-dominio.com
```

Pruebas backend/frontend:

```powershell
.\scripts\run-tests.cmd
```

## Entrega

Generar reporte de estado:

```powershell
.\scripts\make-status-report.cmd
```

Generar ZIP fuente y manifiesto SHA256:

```powershell
.\scripts\make-release.cmd
```

Generar entrega completa validada en un solo comando:

```powershell
.\scripts\make-delivery.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
```

Generar evidencia UAT lista para diligenciar:

```powershell
.\scripts\make-uat-evidence.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
```

Generar carpeta lista para entregar al equipo UAT:

```powershell
.\scripts\make-uat-kit.cmd -ProjectName "Piloto InfoMatt360" -Environment "Local"
```

Este comando genera resumen UAT, carpeta editable y un `.zip` compartible del
kit UAT, ambos en `..\outputs`.

Generar resumen de avance/cierre de la evidencia UAT:

```powershell
.\scripts\summarize-uat-evidence.cmd
```

Ejecutar pre-UAT tecnica antes de la validacion con usuarios:

```powershell
.\scripts\run-uat-technical-checks.cmd
```

Validar que el paquete, manifiesto SHA256, reporte y evidencia UAT esten alineados:

```powershell
.\scripts\check-uat-readiness.cmd
```

Los archivos quedan en:

```text
..\outputs
```

## Produccion

Antes de produccion real:

- configurar `SECRET_KEY` fuerte;
- usar PostgreSQL, no SQLite;
- activar HTTPS y cookies `secure`;
- configurar SMTP;
- configurar CORS explicito;
- usar Redis para rate limiting/throttling distribuido si hay multiples workers/replicas;
- ejecutar migraciones Alembic como paso de deploy;
- separar worker bulk del proceso web;
- conectar metricas a Prometheus/OpenTelemetry si se requiere operacion industrial;
- revisar la guia [docs/61_DESPLIEGUE_PRODUCCION_REFERENCIA.md](docs/61_DESPLIEGUE_PRODUCCION_REFERENCIA.md);
- completar el checklist [docs/62_CHECKLIST_GO_LIVE.md](docs/62_CHECKLIST_GO_LIVE.md);
- definir backup/restauracion con [docs/63_BACKUP_RESTORE_POSTGRES.md](docs/63_BACKUP_RESTORE_POSTGRES.md).
- preparar rollback con [docs/64_ROLLBACK_OPERATIVO.md](docs/64_ROLLBACK_OPERATIVO.md).
- operar monitoreo/incidentes con [docs/65_OPERACION_MONITOREO_INCIDENTES.md](docs/65_OPERACION_MONITOREO_INCIDENTES.md).
- operar tareas funcionales del administrador con [docs/66_RUNBOOK_ADMIN_FUNCIONAL.md](docs/66_RUNBOOK_ADMIN_FUNCIONAL.md).
- documentar la revision funcional local con [docs/67_REVISION_FUNCIONAL_LOCAL.md](docs/67_REVISION_FUNCIONAL_LOCAL.md).
- ejecutar piloto UAT con [docs/68_PLAN_PILOTO_UAT.md](docs/68_PLAN_PILOTO_UAT.md).
- registrar evidencia UAT con [docs/69_PLANTILLA_EVIDENCIA_UAT.md](docs/69_PLANTILLA_EVIDENCIA_UAT.md).
- ejecutar escenarios por modulo con [docs/70_GUIA_EJECUCION_UAT_MODULOS.md](docs/70_GUIA_EJECUCION_UAT_MODULOS.md).

## Modulos de alineacion con la especificacion original (fases 0-4)

- organizaciones y tenant logico: [docs/71_ORGANIZACIONES_TENANT_LOGICO.md](docs/71_ORGANIZACIONES_TENANT_LOGICO.md);
- marca blanca dinamica: [docs/72_MARCA_BLANCA_DINAMICA.md](docs/72_MARCA_BLANCA_DINAMICA.md);
- instalador de primer arranque: [docs/73_INSTALADOR_SETUP_WIZARD.md](docs/73_INSTALADOR_SETUP_WIZARD.md);
- QR de enrolamiento por gestor: [docs/74_QR_ENROLAMIENTO_GESTOR.md](docs/74_QR_ENROLAMIENTO_GESTOR.md);
- correo autoconfigurado: [docs/75_CORREO_AUTOCONFIGURADO.md](docs/75_CORREO_AUTOCONFIGURADO.md);
- carga masiva Excel con mapeo y aprobacion: [docs/76_CARGA_MASIVA_EXCEL_MAPEO.md](docs/76_CARGA_MASIVA_EXCEL_MAPEO.md);
- anti-duplicidad: [docs/77_ANTI_DUPLICIDAD.md](docs/77_ANTI_DUPLICIDAD.md);
- backups programables desde la web: [docs/78_BACKUPS_PROGRAMABLES_WEB.md](docs/78_BACKUPS_PROGRAMABLES_WEB.md);
- conector Google Drive (OAuth): [docs/79_CONECTOR_GOOGLE_DRIVE.md](docs/79_CONECTOR_GOOGLE_DRIVE.md);
- generador de actas PDF: [docs/80_GENERADOR_ACTAS_PDF.md](docs/80_GENERADOR_ACTAS_PDF.md);
- importador XLSForm/ODK/KoboToolbox: [docs/81_IMPORTADOR_XLSFORM_ODK_KOBO.md](docs/81_IMPORTADOR_XLSFORM_ODK_KOBO.md);
- aplicacion de escritorio Electron: [docs/82_APLICACION_ESCRITORIO_ELECTRON.md](docs/82_APLICACION_ESCRITORIO_ELECTRON.md);
- PWA instalable y offline: [docs/83_PWA_OFFLINE_INSTALABLE.md](docs/83_PWA_OFFLINE_INSTALABLE.md);
- ERP headless (inventario y honorarios): [docs/84_ERP_HEADLESS_INVENTARIO_NOMINA.md](docs/84_ERP_HEADLESS_INVENTARIO_NOMINA.md).

Validar configuracion productiva:

```powershell
.\scripts\doctor-production.cmd -EnvFile .env.production
```

Receta de despliegue de referencia:

```powershell
docker compose -f docker-compose.production.example.yml --env-file .env.production up -d --build
```
