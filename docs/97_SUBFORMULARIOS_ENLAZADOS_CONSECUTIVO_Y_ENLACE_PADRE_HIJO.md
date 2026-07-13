# 97. Subformularios enlazados de verdad, consecutivo autoincremental y enlace real padre-hijo

## Qué cierra esto

En la confirmación del estado de los formularios (ver [docs/94](94_IMPORTADOR_MULTIFORMATO.md)) se identificaron 3 brechas honestas frente a las herramientas de referencia:

1. `REPEAT` es un grupo embebido en el mismo `RuntimeRecord` (estilo Kobo/ODK), **no** una entidad hija enlazada de verdad como en ActivityInfo.
2. No existía auto-incremento de consecutivo (`serial_number`).
3. `PARENT_CHILD` no tenía ninguna lógica de enlace real -- se exportaba como texto plano y no hacía nada en Runtime.

Este trabajo cierra las 3, sin tocar `REPEAT` (que sigue siendo la opción correcta para grupos repetibles simples, tipo "integrantes del hogar" cuando no se necesita consultarlos como registros independientes).

## 1. `LINKED_SUBFORM` -- subformularios enlazados de verdad

A diferencia de `REPEAT`, cada fila de un campo `LINKED_SUBFORM` es un **`RuntimeRecord` propio**, capturado con su propia plantilla hija (elegida en el constructor), y enlazado al padre mediante dos columnas nuevas en `runtime_records`:

- `parent_record_id`: id del registro padre.
- `parent_field_name`: nombre del campo `LINKED_SUBFORM` del padre que contiene esta fila.

Los valores del padre **no** incluyen el campo `LINKED_SUBFORM` en su propio JSON -- las filas hijas se consultan aparte.

### Backend

- Migración `0060_runtime_record_parent_link.py`.
- `POST /api/v1/runtime/save` acepta `parent_record_id` y `parent_field_name` opcionales. Si se envía `parent_record_id`, se valida que el registro padre exista y pertenezca al mismo proyecto (404/403 si no).
- `GET /api/v1/runtime/record/{record_id}/children/{field_name}` lista las filas hijas de un campo.
- Config del componente en el Builder: `{"child_template_id": "<id de la plantilla hija>"}`.

### Frontend

- **Constructor**: al elegir "Subformulario enlazado" en la paleta, se puede seleccionar la plantilla hija entre los formularios existentes del proyecto.
- **Captura inicial** (Runtime): el campo muestra un aviso de que hay que guardar el registro primero -- es una limitación real de la arquitectura (una fila hija necesita que el padre ya exista con un id), no una omisión.
- **Pantalla de Registros**: al expandir un registro que tiene campos `LINKED_SUBFORM`, aparece la sección "Subformularios enlazados" con una tabla de las filas hijas existentes y un botón "Agregar fila" que abre el formulario de la plantilla hija y guarda la fila como un registro independiente.

## 2. `SERIAL_NUMBER` -- consecutivo autoincremental

Un campo de tipo `SERIAL_NUMBER` se asigna automáticamente al guardar: el backend calcula `MAX(valor existente para ese campo en esa plantilla) + 1`. Si el capturador ya envía un valor no vacío para ese campo, se respeta (no se sobreescribe) -- útil para reimportaciones o correcciones manuales.

**Limitación conocida:** no hay bloqueo de fila (`SELECT ... FOR UPDATE`); dos guardados simultáneos sobre la misma plantilla podrían calcular el mismo siguiente número. Es una limitación aceptada, consistente con el resto del proyecto (SQLite en desarrollo no soporta ese tipo de bloqueo de forma práctica).

## 3. `PARENT_CHILD` -- enlace real a otro registro

Antes, este tipo no tenía ninguna lógica -- solo existía como categoría y se exportaba como texto. Ahora:

- Config del componente: `{"linked_template_id": "<plantilla enlazada>", "label_field": "<campo mostrado como etiqueta>"}`.
- En Runtime se renderiza como un selector con búsqueda que consulta los registros existentes de `linked_template_id` (reutilizando `GET /runtime/template/{id}/records/search`) y guarda el **id del registro enlazado** como valor del campo -- no texto libre.

## Qué sigue sin resolver (honestidad, no alcance de este cambio)

- No hay endpoint para "editar" una fila hija ya creada de un `LINKED_SUBFORM` (solo crear y listar) -- sería la extensión natural si se necesita.
- El selector de `PARENT_CHILD` no valida en el backend que el id guardado exista realmente en `linked_template_id` -- se guarda como cualquier otro valor de campo. Si se necesita integridad referencial estricta, sería un cambio adicional.
- En XLSForm, ambos tipos exportan como aproximaciones (`SERIAL_NUMBER` → `calculate`, `LINKED_SUBFORM` → `text`) porque el formato plano no puede representar una relación real entre plantillas -- ver `docs/93`.

## Pruebas

`backend/tests/test_linked_subform_and_serial_number.py` (5 pruebas): consecutivo se asigna e incrementa, no se sobreescribe si ya viene provisto, una fila hija de `LINKED_SUBFORM` es un registro separado y no queda embebida en el padre, se rechaza un `parent_record_id` de otro proyecto o inexistente.

## Verificación en vivo

Contra el backend real de la demo: se crearon 2 plantillas (`Hogar` con `SERIAL_NUMBER`+`LINKED_SUBFORM`+`PARENT_CHILD`, `Integrantes del hogar` como hija), se capturaron 2 registros de `Hogar` (consecutivo 1 y 2 confirmados), un `PARENT_CHILD` enlazando el segundo hogar al primero, y 2 filas hijas reales (`Ana`, `Luis`) bajo el primer hogar -- confirmado que no quedan embebidas en el JSON del padre. La pantalla de Registros mostró correctamente la sección "Subformularios enlazados" con la tabla de hijos. El constructor visual mostró los 3 nuevos tipos en la paleta con sus paneles de configuración. Los datos de prueba se eliminaron de la base de datos de la demo al finalizar.
