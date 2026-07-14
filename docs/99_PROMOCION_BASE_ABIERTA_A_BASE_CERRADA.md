# 99. Promoción de base abierta a base cerrada

## Qué cierra esto

El propósito central de InfoMatt360, según lo describió el usuario, es resolver la transición entre dos modalidades de datos:

- **Base de entrada abierta**: escenarios sin registro previo de participantes, donde la información se clasifica e integra a medida que se captura.
- **Base cerrada (participantes preexistentes)**: registros con los que ya se cuenta, alimentada tanto por captura interna como por importación masiva (Excel/CSV, ver `excel_import_service.py`), siempre con validación automática.

Antes de este cambio, ambas piezas existían por separado (formularios públicos sin cuenta para captura abierta, `Participant` + importación masiva para la base cerrada, y el enlace automático de [docs/98](98_PARTICIPANTE_COMO_EJE_CENTRAL.md)), pero faltaba la pieza que las conecta: **una acción explícita para tomar un registro capturado en modo abierto y consolidarlo en la base cerrada**. El enlace automático de docs/98 deliberadamente nunca crea un participante nuevo (para evitar participantes fantasma por errores de digitación) — esta es esa acción, siempre humana.

## Nota sobre el redeploy de KoboToolbox (formularios, no participantes)

El usuario también pidió revisar cómo KoboToolbox estructura su redeploy/versionado de formularios para "centralizar todo en una única tabla descargable" sin fragmentar datos entre tablas nuevas por cada actualización. Esto **ya está resuelto** desde antes de esta sesión de trabajo: ver [docs/95](95_REEMPLAZO_DE_PLANTILLA_EN_EL_MISMO_LUGAR.md) — reemplazar una plantilla conserva el mismo `template_id` (nunca crea una tabla/plantilla nueva), los valores capturados se identifican por nombre de campo (no por una referencia rígida al componente visual, así que sobreviven al reemplazo), y cada reemplazo archiva automáticamente un respaldo de la versión anterior (`BuilderVersion`) como control de versiones. Esa pieza no necesitó cambios adicionales aquí.

## Cómo funciona la promoción

`POST /participants/promote` recibe `record_id` y, o bien:

- `participant_id`: enlaza el registro a un participante **ya existente** del mismo proyecto (por ejemplo, para corregir un caso donde el enlace automático por documento no encontró coincidencia por un error de digitación), o
- `full_name` (+ opcionalmente `document_id`, `external_code`): crea un participante **nuevo** en la base cerrada y enlaza el registro a él.

Reglas:
- Requiere permiso `records.review` o `records.approve` — es una acción de consolidación/revisión, no de captura.
- Rechaza con `409` si el registro ya tiene un participante enlazado (la promoción es de una sola vía; para corregir un enlace ya hecho habría que construir una acción distinta, no incluida aquí).
- Rechaza con `404` si el participante indicado no existe en el proyecto del registro.
- Al crear uno nuevo, reutiliza `participant_service.create_participant()`, así que la validación de duplicado por documento (`409` si ya existe otro participante con el mismo `document_id` en el proyecto) se aplica igual que en la creación manual.

## Descubribilidad: filtro "sin participante enlazado"

`GET /runtime/template/{id}/records/search` acepta `unlinked_only=true`, que filtra a los registros de base abierta que todavía no se enlazaron a ningún participante — son los candidatos a promover. En la pantalla de Registros (`/records/{template_id}`) aparece como el checkbox "Sin participante enlazado" junto a los demás filtros.

## Frontend

En cada registro expandido (tabla de Registros o el enlace mágico de corrección) que **no** tenga `participant_id`, aparece el panel "Base abierta: sin participante enlazado" con dos modos — enlazar a uno existente (selector poblado desde `GET /participants/project/{id}`) o crear uno nuevo (nombre, documento, código externo). Al promover, el panel desaparece del registro (ya no aplica) y el mensaje confirma la acción.

## Qué sigue sin resolver (honestidad, no alcance de este cambio)

- No hay forma de deshacer una promoción desde la UI (desenlazar un registro ya promovido) — habría que hacerlo manualmente en base de datos.
- No hay una pantalla dedicada de "bandeja de promoción" que agregue todos los registros sin enlazar de **todas** las plantillas de un proyecto a la vez — hoy se revisa plantilla por plantilla usando el filtro.
- No existe todavía un flag formal de "modo abierto" vs. "modo cerrado" por proyecto/plantilla que cambie el comportamiento de validación al capturar (por ejemplo, exigir que el registro coincida con un participante antes de aceptar la captura). Lo que existe es la promoción posterior explícita descrita aquí.

## Pruebas

`backend/tests/test_participant_promote.py` (6 pruebas): crear participante nuevo desde un registro, enlazar a uno existente, rechazar promover un registro ya enlazado (409), exigir el permiso de revisión (403 sin él), exigir `participant_id` o `full_name` (422), y el filtro `unlinked_only` en la búsqueda de registros.

## Verificación en vivo

Contra el backend real de la demo: se creó una plantilla de "base abierta" sin participante preasignado, se capturaron 2 registros sin enlazar, se confirmó que el filtro `unlinked_only=true` los encontraba, se promovió el primero creando un participante nuevo (confirmando que desaparece del filtro y aparece en su historial unificado), y se promovió el segundo **desde el navegador real** (no solo por API) enlazándolo al participante recién creado — el panel mostró la lista real de participantes del proyecto, la promoción confirmó con el mensaje esperado, y el panel desapareció del registro tras enlazarlo. Se confirmó también que un segundo intento de promover un registro ya enlazado se rechaza con 409. Los datos de prueba se eliminaron de la base de datos de la demo al finalizar.
