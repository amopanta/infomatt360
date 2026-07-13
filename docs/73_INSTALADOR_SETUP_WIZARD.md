# Instalador de primer arranque (Setup Wizard)

## Objetivo

Permitir que un despliegue nuevo de InfoMatt360 cree su primera
organizacion, proyecto y usuario administrador desde el navegador, sin
requerir un script de seed manual -- y dejar tambien correo, almacenamiento
y backups listos desde el mismo asistente, en vez de exigir tres visitas
adicionales a pantallas separadas despues de instalar.

## Estado por defecto: inerte

El instalador solo bloquea el sistema cuando `installer_enforced=true` en la
configuracion (`backend/app/core/config.py`, por defecto `False`). Con el
flag desactivado, `GET /api/v1/install/status` siempre reporta
`installed: true` y el middleware no interfiere con ningun despliegue
existente. Este es el estado actual de la demo e instalaciones ya
configuradas por seed.

## Modelo

`InstallationState` (`backend/app/models/installation.py`): tabla singleton
(una sola fila). Su ausencia se interpreta como "instalado" cuando
`installer_enforced` esta desactivado.

## Flujo (wizard multi-paso)

`frontend/src/modules/install/InstallWizardApp.tsx` ya no es un formulario
unico: son 7 pasos con indicador de progreso, navegables con
"Atras"/"Siguiente".

1. **Requisitos del servidor** — `GET /api/v1/install/requirements`.
   Verifica conexion a la base de datos (`SELECT 1` contra la que ya quedo
   configurada por `DATABASE_URL`), que el directorio de subida de
   archivos exista y sea escribible, que `SECRET_KEY` no sea el valor de
   desarrollo por defecto, y advierte si el motor es SQLite en produccion.
   Expuesto bajo `/api/v1/install/*` (no bajo `/api/v1/health/*`) porque
   ese es el unico prefijo que el `InstallGuardMiddleware` deja pasar
   antes de completar la instalacion.
2. **Organizacion** — nombre, slug (autogenerado desde el nombre, editable)
   y una URL publica opcional (`Organization.public_url`, migracion
   `0059_organization_public_url.py`).
3. **Administrador y primer proyecto** — igual que antes.
4. **Correo (opcional)** — si se activa, crea un `MailProfile` con
   `sender_email`/`server_host`/`server_port` directamente en el bootstrap.
5. **Almacenamiento (opcional)** — si se activa (por defecto si), crea un
   `StorageProfile` local con el limite de tamano de archivo indicado.
6. **Backups (opcional)** — si se activa, crea un `ScheduledTask`
   (`task_type="backup"`, `frequency` hourly/daily/weekly) con
   `next_run_at` inmediato, para que el worker programado
   (`docs/78_BACKUPS_PROGRAMABLES_WEB.md`) lo recoja en el siguiente ciclo.
7. **Confirmar** — resumen de todo lo anterior antes de enviar.

`POST /api/v1/install/bootstrap` (sin autenticacion, por diseno: se usa
antes de que exista ningun usuario) crea todo en una sola transaccion:
`Organization` + `Project` + `Role` "Administrador" (`ALL_PERMISSIONS`) +
`User` administrador + su asignacion, mas los `MailProfile`/
`StorageProfile`/`ScheduledTask` opcionales, y marca
`InstallationState.is_installed=true`. Reintentar despues de instalado
devuelve `409 Conflict` — la operacion es de una sola vez.

## Por que no hay un paso para "configurar la base de datos"

El motor de SQLAlchemy ya quedo creado con `DATABASE_URL` cuando el proceso
arranco (`backend/app/db/session.py`); no hay forma de cambiar la conexion
en caliente sin reiniciar el proceso con otra variable de entorno. A
diferencia de un CMS en PHP que relee su config en cada peticion, un
proceso Python de larga duracion no puede "reconfigurar la base de datos"
desde un formulario web sin mentir sobre lo que realmente pasa. Por eso el
paso 1 del wizard **verifica** la conexion ya configurada en vez de ofrecer
cambiarla — ver `installation_service.requirements()`.

## Activar el instalador

Para forzar el flujo completo (por ejemplo, para probarlo o en un
despliegue nuevo sin seed): `installer_enforced=true` en `.env` del backend,
y no ejecutar `seed_demo.py` antes del primer arranque.

## Limites conocidos

- No hay wizard para agregar organizaciones adicionales a un sistema ya
  instalado (usar `POST /api/v1/organizations/` directamente).
- El estado "instalado" es global al backend, no por organizacion.
- El paso de almacenamiento solo ofrece "local" inline; conectores en la
  nube (S3/MinIO/Google Drive) siguen requiriendo credenciales y, en el
  caso de Drive, un flujo OAuth — se configuran despues en `/admin/storage`
  (`docs/79`, `docs/89`), que ya tiene pantalla propia para eso.
- La URL publica de la organizacion (`Organization.public_url`) es
  metadata informativa de la organizacion; el dominio real por el que se
  sirve la aplicacion sigue dependiendo del despliegue/proxy inverso, no
  de este campo.

## Verificacion

`backend/tests/test_installation.py` (5 tests): estado con instalador
desactivado, rechazo de bootstrap sin instalador activo, requisitos del
servidor (base de datos y directorio de subida en `ok`), creacion completa
del stack administrativo con login real, e idempotencia (`409` en el
segundo intento), y creacion de los tres pasos opcionales (correo,
almacenamiento, backups) verificando cada fila creada en la base de datos.
