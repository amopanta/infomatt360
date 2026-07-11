# Notas de version MVP

## Alcance incluido

- Autenticacion con recuperacion de contrasena, cambio de contrasena y sesiones con refresh token.
- Administracion segura de usuarios: correccion de correo, reinicio de contrasena temporal, invalidacion de sesiones y reset MFA.
- MFA TOTP opcional con codigos de recuperacion.
- Constructor de formularios con catalogo amplio de campos, validaciones, formulas, pulldata y datos externos.
- Runtime web para captura de registros, repetidores, evidencia, geocampos y firma.
- Registros con busqueda, filtros, paginacion y exportacion CSV segura.
- Reportes por proyecto con resumen operativo y exportacion XLSX.
- Mapa operativo consolidado desde entidades GIS y registros capturados.
- Auditoria visible por usuario/proyecto con control de alcance.
- Datos demo, smoke test local, health/readiness y preflight.
- Flujos de aprobacion configurables desde panel administrador.
- API keys, perfiles de rate limiting y sincronizacion bulk con worker, backoff, heartbeat operativo y panel admin de seguimiento.
- Observabilidad operativa con metricas p50/p95/p99, panel admin, alertas visuales, salida Prometheus, trazabilidad `X-Request-ID` y permisos de acceso.
- Menu y rutas administrativas filtradas por permisos del proyecto activo.
- Referencia de despliegue productivo con Docker Compose, PostgreSQL, Redis, frontend nginx, backend y worker bulk separado.
- Checklist go-live para seguridad, base de datos, Redis, worker bulk, observabilidad, validacion funcional y rollback.
- Script `check-production-package.cmd` para validar artefactos productivos de referencia.
- Scripts y guia de backup/restauracion PostgreSQL con `pg_dump` y `pg_restore`.
- Guia de rollback operativo para volver a una version estable con backup, logs y validaciones.
- Monitor liviano de salud y guia de operacion/incidentes.
- Runbook funcional para administradores de proyecto.
- Guia de revision funcional local con alcance automatizado y checklist manual.
- Validacion CORS local para navegador en `localhost` y `127.0.0.1`.
- Contrato de rutas frontend testeado para navegacion y permisos administrativos.
- Confirmaciones frontend antes de operaciones administrativas sensibles: cambiar correo, reiniciar contrasena, reiniciar MFA, revocar API key y procesar lotes bulk manualmente.
- Documentacion historica actualizada para reflejar access token en memoria, refresh cookie httpOnly, CORS local y conteo vigente de pruebas.
- Plan piloto UAT con escenarios de aceptacion, evidencia minima y criterios de salida.
- Plantilla de evidencia UAT para registrar escenarios, hallazgos, decision y acta de cierre.
- Guia de ejecucion UAT por modulos con pasos, evidencias y criterios de aprobacion.
- Script para generar evidencia UAT diligenciable con version ZIP y SHA256 del ultimo paquete.
- Script para validar que ZIP, SHA256, reporte de estado y evidencia UAT correspondan entre si.
- Script de entrega completa para ejecutar preflight, reporte, empaquetado, evidencia UAT y revision final en un solo comando.
- Script para generar un kit UAT compartible en carpeta y ZIP con SHA256, reporte, evidencia, resumen y guias funcionales.
- Script para resumir automaticamente evidencia UAT y sugerir decision de cierre.
- Script de pre-UAT tecnica para mapear pruebas automaticas contra escenarios UAT.
- Paquete fuente de entrega con ZIP limpio y manifiesto SHA256.

## Validacion actual

- Backend: suite automatizada completa.
- Frontend: tests Vitest y build Vite cuando `node_modules` esta instalado; sintaxis TypeScript offline como respaldo.
- Full stack local: backend, frontend preview, health/readiness y smoke test demo por API validado con `scripts/check-full-stack.cmd`.
- Scripts PowerShell: validacion de parseo.
- Paquete: excluye `.git`, `.venv`, `node_modules`, `dist`, caches, `uploads`, `.env` y bases locales.

## Pendiente industrial

- Pruebas de carga con volumen real.
- Migracion gradual a SQLAlchemy async + asyncpg si las metricas muestran cuello de botella.
- Ampliar OpenTelemetry/tracing distribuido.
- Adaptar la receta productiva al proveedor final: dominio, HTTPS, backups, secretos, monitoreo y pipeline CI/CD.
