# Anti-duplicidad de participantes y registros

## Objetivo

Reducir datos duplicados en dos puntos distintos del sistema, con dos
estrategias distintas segun que tan confiable es la senal de duplicado:

- **Participantes**: bloqueo duro por documento de identidad repetido.
- **Registros de formulario (`RuntimeRecord`)**: marcado de posible
  duplicado por contenido similar, sin bloquear (requiere criterio humano).

## Participantes: bloqueo duro

`participant_service.create_participant()`
(`backend/app/services/participant_service.py`) verifica, antes de
insertar, si ya existe un `Participant` con el mismo `document_id` **en el
mismo proyecto**. Si existe, devuelve `409 Conflict` ("Ya existe un
participante con este documento en el proyecto") y no crea el registro.
Justificacion: un documento de identidad duplicado en el mismo proyecto es
casi siempre un error de captura, no un caso legitimo a revisar.

## Registros de runtime: marcado para revision

`runtime_record_service.py` no puede bloquear del mismo modo porque dos
envios legitimos pueden compartir mucho contenido (mismo formulario, mismo
encuestador, mismo dia). En su lugar:

1. Calcula un `content_hash` de los valores del formulario
   (`_compute_content_hash(project_id, template_id, values)`).
2. Busca si existe otro `RuntimeRecord` con el mismo `project_id`,
   `template_id` y `content_hash`, creado dentro de una ventana de tiempo
   configurable (`settings.duplicate_check_window_days`).
3. Si existe, el nuevo registro se guarda igual, pero con
   `duplicate_flag="possible"` en vez de `"none"`. No se bloquea el envio.

## Campo `duplicate_flag`

Agregado (migracion `0044_duplicate_flags.py`) tanto en `Participant` como
en `RuntimeRecord`, con valores `none` / `possible` / `confirmed_unique`.
`confirmed_unique` esta reservado para un flujo de revision manual (marcar
"no es duplicado" tras inspeccion humana) que aun no tiene endpoint propio.

## Limites conocidos

- No hay endpoint todavia para que un revisor cambie `possible` a
  `confirmed_unique` o confirme el duplicado; el campo se expone en
  lectura (`ParticipantRead`/`RuntimeRecordRead`) pero su triage queda
  pendiente de una pantalla de revision.
- El bloqueo de participantes es por proyecto, no global: el mismo
  documento puede existir en distintos proyectos sin conflicto.
