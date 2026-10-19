# 142. Validación e implementación de las funcionalidades de docs/141

Fecha: 2026-10-18. Rama: `feature/hybrid-offline-capture-20261017`.
Fuente: `INFO_MATT_360_Funcionalidades_Adicionadas_y_Plan_de_Implementacion.docx`, docs/140_DEVOLUCIONES… y docs/141.

## Matriz: qué había y qué se construyó

| § | Funcionalidad | Antes | Ahora |
|---|---|---|---|
| 2 | Paginación diseñada por el constructor; REPEAT dentro de su sección | Existía en web y app | Igual. **Nuevo:** el borrador retoma la página donde quedó (web y app) |
| 3 | Ficha del participante sin conexión | Ficha, asignaciones y estados (H02) | **Nuevo:** respuestas previas en solo lectura, también de otros equipos (máx. 300 por paquete; archivos listados, no descargados) |
| 4 | Estados y responsabilidades | Se editaba un registro **enviado**; cualquier gestor con `records.write` corregía un devuelto | Enviado, en revisión y aprobado son de solo lectura. Un devuelto lo corrige y reenvía **solo su destinatario**. El autor (`submitted_by`) nunca cambia |
| 5 | Devolución individual y masiva, reasignar | Devolución solo al autor | `POST /review/records/{id}/return`: al autor o a otro gestor (se valida acceso, permiso de captura y territorio). `POST /review/bulk-returns/{proyecto}`: Excel/CSV con vista previa, validación previa, resultados por fila, archivo de errores e idempotencia |
| 6 | Observaciones por pregunta y REPEAT, con estados | Una nota y un campo por devolución | Tabla `review_observations` (pregunta, ruta REPEAT, evidencia, motivo, acción) con estados pendiente → en corrección → corregida → verificada/rechazada. Panel web "Validación y retroalimentación"; en la tablet, aviso con "Ir a la pregunta" y "Ya la corregí" |
| 7 | Sincronización diferencial y corrección en otra tablet | La app no recibía devueltos | `/review/my-corrections` y `/records/{id}/correction-package`. Con la misma versión solo bajan las observaciones; si no, bajan respuestas, integrantes REPEAT y solo los adjuntos que faltan. Se envían solo los campos cambiados con `expected_lock_version`; un conflicto se conserva sin sobrescribir |
| 8 | Dos exportaciones independientes | CSV de observaciones desde las notas de revisión (commits del 18-oct) | `clean-export.csv`: una fila por registro, sin observaciones, **aprobados por defecto**, filtro de periodo y territorio. `observations.csv` con las observaciones estructuradas. Botones en la lista de registros |

## Pruebas de aceptación (docs/141 §11)

| Criterio | Dónde |
|---|---|
| Formulario de 350+ preguntas con páginas, REPEAT y condicionales | `test_large_form_350_questions…`: 355 preguntas en 10 secciones, REPEAT de 15 campos con 4 integrantes |
| Bloqueo efectivo | `test_return_reassign…` y `test_submitted_and_approved_are_read_only` |
| Devolución masiva de 1.000 filas con errores parciales y reintento | `test_bulk_return_1000_rows…`: 10 errores, 1 duplicada, 493 registros devueltos; el reintento no duplica |
| Reasignación a otra tablet sin cambiar el autor | Servidor: `test_return_reassign…`. App: `test/corrections.test.ts`. **Emulador:** la web devolvió a la gestora; su tablet corrigió sin red y reenvió a los 15 s de reconectar |
| Devolución al dispositivo original sin bajar archivos de nuevo | `test/corrections.test.ts`: la segunda sincronización baja solo las observaciones |
| Conflictos sin sobrescritura | `test/corrections.test.ts` (409 → "en conflicto", con los cambios conservados) |
| Exportación limpia sin observaciones ni filas repetidas | `test_clean_export_defaults…` y `test_return_reassign…` |

Los barridos de seguridad (docs/140 §10) se extendieron a las rutas y tablas
nuevas (observaciones), entre proyectos y por territorio, y siguen limpios.

## Decisiones tomadas

- **La reapertura de un aprobado** es la excepción administrativa: el administrador puede designar quién corrige, e incluso designarse a sí mismo, y queda registrado.
- **Al reenviar**, el gestor marca las observaciones como "corregida", pero solo un revisor puede verificarlas o rechazarlas.
- **Devolución masiva:**
  - varias filas del mismo registro se aplican como **una** devolución con varias observaciones;
  - si dos filas del mismo registro piden acciones o destinatarios distintos, se marcan como error.

## Pendiente

- La UAT con usuarios reales y un formulario de 350+ preguntas en una tablet física, para medir rendimiento en un equipo real.
- El ícono del menú lateral para la devolución masiva: hoy está dentro de la lista de registros de cada formulario.
- Las devoluciones de los registros de la tabla `records` heredada: las observaciones estructuradas aplican a `runtime_records`.
