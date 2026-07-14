# 98. El participante como eje central

## Qué cierra esto

La auditoría de trazabilidad contra el Documento Maestro de Requerimientos v1.0 (ver [docs/96](96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md), hallazgo #13) identificó esta como la brecha más estructural: el motor de captura real (`RuntimeRecord`) no tenía ningún enlace a un participante. Solo un modelo `Record` separado y aparentemente sin uso en el flujo real (`app/models/records.py`) tenía `participant_id` + `source_channel`, pero ningún código de producción lo poblaba.

Este trabajo cierra la brecha directamente sobre `RuntimeRecord` (el motor real), no sobre ese modelo legado.

## Cómo funciona el enlace

`RuntimeRecord` ahora tiene una columna `participant_id` (migración `0061`). Al guardar un registro (`POST /runtime/save`), se enlaza de dos formas posibles:

1. **Enlace explícito**: si el payload trae `participant_id`, se valida que el participante exista y pertenezca al mismo proyecto (404/403 si no). Útil cuando el formulario ya se abre "sobre" un participante conocido (por ejemplo, un formulario de seguimiento sin campo de documento propio).
2. **Enlace automático por documento**: si no se envía `participant_id`, el backend busca en la plantilla un componente de tipo `DOCUMENT_ID`, toma el valor capturado para ese campo, y busca un `Participant` existente en el mismo proyecto con ese mismo `document_id`. Si lo encuentra, enlaza automáticamente.

**Decisión de diseño importante**: nunca se crea un participante nuevo en este flujo, solo se enlaza a uno que **ya exista**. Crear participantes automáticamente por cada captura generaría participantes fantasma ante errores de digitación del documento. Los participantes se siguen creando explícitamente (`POST /participants/`) o por carga masiva Excel.

## Historial unificado

- `GET /participants/{id}` — datos básicos del participante (corrige además un hueco de aislamiento: antes `get_participant` no filtraba por proyecto).
- `GET /participants/{id}/history` — todos los `RuntimeRecord` enlazados a ese participante, **sin importar la plantilla ni el canal** (web, carga masiva, API, etc.), con el nombre de la plantilla resuelto para mostrarlo en pantalla.

Ambos endpoints devuelven 404 si el participante no existe **o** si pertenece a un proyecto al que el usuario no tiene acceso — deliberadamente no se distingue entre ambos casos para no filtrar qué ids existen en otros proyectos.

## Frontend: módulo Participantes

Pantalla nueva en `/participants` (enlace "Participantes" en el menú lateral, junto a "Formularios"):

- **Lista** (`/participants`): tabla de participantes del proyecto activo, con buscador por nombre/documento/código.
- **Detalle** (`/participants/{id}`): datos del participante + tabla del historial unificado (formulario, estado traducido, fecha, capturado por). Cada fila tiene un enlace "Ver registro" que reutiliza el deep-link ya existente de la pantalla de Registros (`/records/{template_id}?recordId={record_id}`, ver [docs/86](86_INTEROPERABILIDAD_DONANTES.md) y el trabajo de enlace mágico) para abrir el registro exacto.

## Qué sigue sin resolver (honestidad, no alcance de este cambio)

- No hay una pantalla para "asignar" manualmente un registro ya capturado a un participante después del hecho (solo se enlaza al guardar). Si un registro quedó sin enlazar (documento no coincide con ningún participante existente), hoy no hay forma de corregirlo desde la UI.
- El modelo legado `Record`/`RecordEvent` (`app/models/records.py`) sigue sin usarse — no se tocó, ya que el enlace real ahora vive en `RuntimeRecord`. Sería candidato a deprecar formalmente si se confirma que no tiene ningún consumidor.
- El enlace automático solo considera el **primer** componente `DOCUMENT_ID` de la plantilla con valor no vacío; si una plantilla tuviera dos campos `DOCUMENT_ID` (caso raro), solo se evalúa hasta encontrar el primero que coincida con un participante existente.

## Pruebas

`backend/tests/test_participant_history.py` (7 pruebas): enlace explícito, rechazo de participante de otro proyecto o inexistente, enlace automático por documento (con caso de "documento desconocido" que correctamente no enlaza), historial unificado agrupando 2 plantillas distintas, y aislamiento de proyecto en los endpoints de detalle/historial.

## Verificación en vivo

Contra el backend real de la demo: se crearon 2 plantillas (una con campo `DOCUMENT_ID`, otra sin él), un participante, un registro capturado con enlace automático por documento y otro con enlace explícito sobre la segunda plantilla. El historial unificado (`GET /participants/{id}/history`) devolvió correctamente ambos registros agrupados. En el navegador: la lista de participantes mostró el participante creado, el detalle mostró el historial con las 2 plantillas y sus estados traducidos, y el enlace "Ver registro" abrió correctamente el registro exacto en la pantalla de Registros existente. Los datos de prueba se eliminaron de la base de datos de la demo al finalizar.
