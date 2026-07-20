# 116. Bandeja externa de correo vía IMAP

## Qué cierra esto

El ítem #11 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md`, el último de los 14 sin resolver: "Doble bandeja de correo (bandeja interna + bandeja externa vía IMAP) (§12)". Antes de este cambio, `mail_autoconfig_service.py` solo enviaba correo (SMTP); el único "inbox" del código era la mensajería interna usuario-a-usuario (`message_service.list_inbox`), no una bandeja de correo externo leída por IMAP. Con esto se cierran los 11 ítems de docs/96.

**Alcance acordado con el usuario (AskUserQuestion, opción recomendada elegida explícitamente):** bandeja de **solo lectura**. Un perfil IMAP por proyecto, sondeo periódico cada hora (reusando `ScheduledTask`, la granularidad más fina que esa infraestructura soporta hoy), una sola carpeta (INBOX), vista de solo lectura con marcar leído/archivado. Sin adjuntos, sin múltiples carpetas, sin responder desde la app.

## Hallazgo de seguridad corregido de paso

`MailProfile.config_json` (que ya guardaba la contraseña SMTP) se almacenaba en **texto plano**, a diferencia de S3/Mirror/GDrive que cifran sus credenciales con `encrypt_text`/`decrypt_text`. El endpoint de lectura además devolvía `config_json` sin cifrar al cliente — una fuga real vía la pestaña de red del navegador. Como se tocaba esta misma tabla por primera vez para agregar IMAP, se corrigió también el lado SMTP en el mismo cambio: `create_mail_profile` ahora cifra al escribir, `MailProfileRead` dejó de heredar de `MailProfileCreate` (mismo patrón que `StorageProfileRead`) y ya no expone `config_json` en ninguna respuesta. Sin migración de datos: no había filas con `config_json` poblado en el seed/demo, así que el fix es hacia adelante, con un fallback defensivo (`try/except InvalidToken`) por si una fila en texto plano ya existiera en algún entorno de desarrollo suelto.

## Diseño

### Backend

- `backend/app/models/messages.py`: columna `last_imap_uid` en `MailProfile` (watermark, `NULL` = nunca sondeado) y modelo nuevo `ExternalMailMessage` (`UNIQUE(mail_profile_id, uid)` como segunda línea de defensa contra duplicados, además del watermark).
- `backend/alembic/versions/0069_external_mail_messages.py`: migración idempotente por inspección, mismo patrón que `0067`/`0068`.
- `backend/app/services/message_service.py`: `decrypt_mail_config()` (función de módulo, no método), cifrado en `create_mail_profile`, y el CRUD de bandeja externa (`list_external_inbox`, `get_project_external_message`, `set_external_status`).
- `backend/app/services/mail_autoconfig_service.py`: `send_test_email` pasa a usar `decrypt_mail_config` compartido; se eliminó el `_parse_config` privado ahora duplicado.
- `backend/app/services/imap_service.py` (nuevo): `poll_profile(db, profile) -> (status, result_text)`, misma forma que el branch `"backup"` ya esperado por `scheduler_service._execute()`. Usa `imap-tools` (envuelve `imaplib`/`ssl` del stdlib, sin extensiones nativas) para evitar parsear MIME/charset a mano. Sondeo incremental vía `AND(uid=f"{n}:*")` cuando hay watermark, `"ALL"` en el primer sondeo. Un mensaje que falla al interpretarse (p. ej. UID no numérico) no aborta el lote — mismo espíritu "por ítem" ya usado en CSV import, ZIPs de actas/evidencias e impresión en lote de escritorio.
- `backend/app/services/scheduler_service.py`: nueva rama `task_type == "mail_poll"` en `_execute()`, delega a `imap_service.poll_profile`.
- `backend/app/schemas/messages.py`: `MailProfileRead` independiente (sin `config_json`, con `last_imap_uid`), `ExternalMailMessageRead`/`ExternalMailMessageUpdate`.
- `backend/app/api/v1/messages.py`: `GET /external/{project_id}/inbox`, `PATCH /external/{project_id}/{message_id}` — mismo criterio de permiso que el resto del archivo (`user_has_project_access`, sin permiso dedicado nuevo).
- Sin endpoint nuevo para "activar sondeo": `ScheduledTask` ya es genérico, así que activar el sondeo de un perfil IMAP es `POST /scheduler/tasks` con `task_type="mail_poll"`, `target_id=<profile.id>`, `frequency="hourly"`, reusando la ruta existente. `TASK_TYPE_PERMISSIONS` solo tiene entrada para `"backup"`, así que `mail_poll` queda protegido solo por pertenencia al proyecto — mismo criterio sin-permiso-dedicado que ya usa todo `messages.py`. No se agregó ningún permiso nuevo a `app/core/permissions.py`.
- `backend/requirements.txt`: `imap-tools`.

### Frontend

- `frontend/src/modules/messages/MessagesApp.tsx`: tercera pestaña "Bandeja externa" junto a Recibidos/Enviados, componente hermano `ExternalMessageList` (mismo look que `MessageList`, `De: {from_address}` en vez de `sender_id`, sin acción de responder).
- `frontend/src/modules/messages/api.ts`: `fetchExternalInbox`, `markExternalRead`.
- `frontend/src/modules/admin/MailProfilesApp.tsx` + `mailApi.ts`: selector de tipo (Envío SMTP / Bandeja externa IMAP) en el formulario de creación — antes `provider` nunca se enviaba y siempre caía en `"smtp"` por default del backend. Columna "Tipo" y "Estado" nuevas en la tabla; para perfiles IMAP se muestra "Sondeo inactivo"/"Activar sondeo IMAP" o "Sondeo activo (cada hora) — {último resultado}" en vez del botón "Enviar prueba" (que solo tiene sentido para SMTP).
- `frontend/src/modules/admin/schedulerApi.ts`: `createScheduledMailPollTask`, mismo patrón que `createScheduledBackupTask` ya usa `BackupsApp.tsx`.

## Corrección sobre el plan original

Durante el diseño de este ítem se afirmó (y se verificó en ese momento vía Grep/Glob) que `backend/tests/test_messages.py` no existía. Esto era incorrecto: el archivo sí existe (4 pruebas: inbox/sent/counts/read-status interno, autoconfig conocido/desconocido, test-send con 403/detalle de servidor faltante, validación de destinatario) y pasó sin cambios con esta implementación — sirve como confirmación adicional de que los schemas/servicio de mensajería interna quedaron intactos.

## Pruebas

`backend/tests/test_imap_inbox.py` (nuevo, 7 casos, mock de IMAP con `FakeMailBox`/`FakeMailMessage` hecho a mano vía `monkeypatch.setattr(imap_service, "MailBox", FakeMailBox)`, mismo criterio que `FakeS3Client` en `test_s3_storage.py`):

1. Primer sondeo sin `last_imap_uid`: trae todos los mensajes fake, `last_imap_uid` queda en el UID más alto, criterio de fetch es `"ALL"`.
2. Sondeo incremental: con watermark existente, el criterio pasado a `fetch` es `(UID n+1:*)` y solo se traen los UIDs nuevos, sin duplicar los ya existentes.
3. Mensaje mal formado (UID no numérico) no aborta el lote — el resto se persiste, el resultado reporta el conteo omitido.
4. UID duplicado bajo el `UNIQUE` (`IntegrityError`) no rompe el sondeo, se cuenta como omitido, no se pierde el resto del lote.
5. Rutas nuevas: 403 sin acceso al proyecto, 404 al marcar un mensaje que pertenece a otro proyecto del mismo usuario, 200 + `status: "read"` en el caso normal.
6. Wiring del scheduler: `ScheduledTask(task_type="mail_poll", ...)` vencido + `imap_service.poll_profile` mockeado (esta prueba solo valida el cableado, no el cliente IMAP) → `run_due_tasks` reporta `{"processed": 1, "succeeded": 1, "failed": 0}` y crea un `TaskRun`.
7. Cifrado: perfil creado con contraseña real vía la API → la fila cruda en la base tiene `config_json` cifrado (`decrypt_text` la recupera correctamente) y ninguna respuesta HTTP (creación ni listado) expone `config_json`.

Suite completa: `pytest -q` → **420 passed**, más los 5 errores ya conocidos y no relacionados (`test_file_upload.py` x3, `test_health.py` x2 — bloqueo de directorio temporal de Windows, ver [[project_pytest_cache_lock_issue]] en memoria, no es una regresión). Frontend: `tsc --noEmit` limpio, `vitest run` → **101/101** (sin pruebas nuevas — el cambio de frontend es únicamente wiring de UI sobre tipos/endpoints ya cubiertos por las pruebas de backend), `npm run build` limpio.

## Verificación en vivo

Contra la demo real (`admin@infomatt360.demo`, proyecto `demo-project-infomatt360`), con `backend/.env`/`frontend/.env.local` temporales y la migración `0069` aplicada a la base demo (`alembic upgrade head`):

- Se creó un perfil de correo real con tipo "Bandeja externa de solo lectura (IMAP)" desde `MailProfilesApp.tsx` — el formulario cambió correctamente sus etiquetas y placeholders (Servidor IMAP, puerto 993, "Casilla a leer") al seleccionar el tipo.
- La tabla de perfiles mostró correctamente la fila nueva: columna "Tipo" = "IMAP (lectura)", columna "Estado" = "Sondeo inactivo", con el botón "Activar sondeo IMAP" (en vez de "Enviar prueba").
- Clic en "Activar sondeo IMAP" → mensaje real "Sondeo IMAP activado: se ejecuta cada hora desde el worker de tareas programadas."; la tabla pasó a "Sondeo activo (cada hora) — aún sin ejecutar"; confirmado por red que se disparó un `POST /api/v1/scheduler/tasks` real (200 OK) seguido de un refresco `GET /api/v1/scheduler/tasks/demo-project-infomatt360`.
- En `/messages`, la pestaña "Bandeja externa" cargó sin errores de consola, con el texto explicativo correcto y "No hay mensajes en la bandeja externa todavía."; confirmado por red que golpeó `GET /api/v1/messages/external/demo-project-infomatt360/inbox` real (200 OK).
- Esto valida el pipeline completo de UI + API + scheduler (creación de perfil, cifrado en tránsito ya cubierto por pytest, activación de tarea programada, carga de la bandeja) sin tráfico IMAP real — límite explícito, no fingido: este entorno no tiene una casilla de correo real disponible, así que la conexión IMAP real (`imap_service.poll_profile` contra un servidor de verdad) queda cubierta solo por la suite de pytest mockeada más revisión de código, pendiente de una prueba manual futura con credenciales de una cuenta desechable si el usuario decide proveerlas.
- Se eliminó el perfil y la tarea programada de prueba directo en la base de datos demo (no existen endpoints DELETE para ninguno de los dos); se revirtieron `backend/.env` (línea `CORS_ALLOWED_ORIGINS`) y se eliminó `frontend/.env.local`.

## Lo que queda fuera de esta sesión

Con esto se cierran los 11 ítems de `docs/96` (#1-#11). Lo que sigue abierto en el proyecto son follow-ons ya documentados dentro de ítems individuales (motores MySQL/SQL Server y modo incremental para el ítem #1 de Base Espejo; tipos de campo complejos — archivos, GPS, subformularios, multiselect, calculados — para la importación masiva de registros históricos del ítem #3) y las categorías C/D de la auditoría técnica externa de julio 2026 (balanceador de carga, PgBouncer, observabilidad, pruebas de carga reales; refactors grandes de entidad `User` y migración a SQLAlchemy async), bloqueadas en una decisión de hosting/infraestructura que el usuario aún no ha tomado.
