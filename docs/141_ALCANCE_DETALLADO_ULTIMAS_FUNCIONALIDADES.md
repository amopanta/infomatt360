# INFO-MATT 360 — Alcance detallado de las últimas funcionalidades (octubre de 2026)

**Estado:** requisitos acordados y documentados; desarrollo, pruebas y despliegue pendientes.  
**Relacionado:** [140_DEVOLUCIONES_MASIVAS_SINCRONIZACION_Y_EXPORTACIONES_LIMPIAS.md](140_DEVOLUCIONES_MASIVAS_SINCRONIZACION_Y_EXPORTACIONES_LIMPIAS.md).

## 1. Paginación configurable
El diseñador del formulario determina las páginas, el orden y las secciones; no existe división automática por número de preguntas. Un bloque lógico como «integrantes del núcleo familiar» no se divide entre páginas. Los REPEAT mantienen íntegros sus ítems; matrices, condiciones, adjuntos y referencias entre páginas conservan sus relaciones. Los borradores recuperan la página de trabajo, incluso con formularios de más de 300 preguntas.

## 2. Participante y consulta multidispositivo
El participante es el eje para mostrar actividades asignadas, aplicadas, pendientes y devueltas. Dispositivos autorizados pueden consultar respuestas previas descargadas, incluso sin conexión. La disponibilidad local no implica permiso de edición. Un registro ya aplicado no debe crearse otra vez por otro dispositivo.

## 3. Estados y edición
- **Borrador:** el gestor autorizado edita y guarda.
- **Enviado / en revisión:** solo lectura para el gestor.
- **Devuelto:** edición del **mismo registro** solo por el gestor destinatario de la devolución.
- **Reenviado:** vuelve a bloquearse.
- **Aprobado:** bloqueado para todos en el flujo ordinario. Reapertura excepcional administrativa, si se permite, en flujo separado con auditoría.
No se habilitan «dos ediciones libres» tras enviar. `submitted_by` permanece como autor original aunque otra persona corrija.

## 4. Revisión y retroalimentación por registro
Panel independiente con resultado de validación, observación general, hallazgos por campo, evidencia y por ítem concreto de REPEAT; motivo y corrección requerida. Estados de observación: pendiente, en corrección, corregida, verificada, rechazada. El gestor ve los hallazgos y puede ir directamente a la página y pregunta observadas. Las observaciones no son respuestas del formulario.

## 5. Devolución al gestor original o reasignación
Coordinador (en su ámbito) o administrador elige devolver al capturista o asignar a otro gestor. El nuevo gestor recibe el registro original con respuestas, REPEAT, matrices y evidencias; no un formulario vacío. Solo el destinatario vigente tiene autorización de corrección; se conserva el historial de responsables y valores.

## 6. Devoluciones masivas por Excel
Archivo con `record_id`, acción `RETURN_ORIGINAL|REASSIGN`, `target_user_id` cuando corresponda, observación, campo y motivo. Se permiten varias observaciones por registro. Validación previa de existencia, estado no aprobado, permisos, proyecto, territorio, usuario activo y conflictos. Vista previa, confirmación, idempotencia, procesamiento por lotes y reporte de errores por fila.

## 7. Sincronización inteligente offline
Cada dispositivo mantiene versión del registro, plantilla, estado y manifiesto de adjuntos. Si el destinatario ya posee respuestas y archivos actuales, descargar solo devolución, permisos y observaciones. Si no posee el registro, descargar toda la información necesaria; si tiene una versión anterior, únicamente diferencias y archivos faltantes. La existencia del participante en la tablet **no** demuestra que tenga las respuestas del registro. El servidor revalida permisos, estado y versiones al recibir cambios offline; conflictos no sobrescriben silenciosamente datos oficiales.

## 8. Exportaciones independientes
**Base de respuestas limpia:** preguntas, respuestas y claves técnicas; sin observaciones, devoluciones, motivos, comentarios ni historial. No se multiplican registros por cantidad de observaciones. Filtros por estado, fecha y territorio; para informes oficiales se propone aprobados como opción inicial.

**Base de observaciones:** una fila por hallazgo, con registro, pregunta/ruta REPEAT, motivo, corrección requerida, responsable, fechas y estado. 

**Auditoría:** salida opcional separada con cambios, versiones, revisores y responsables. Todas vinculadas por identificador único de registro.

## 9. Reutilización técnica
Ampliar Runtime, revisión, asignaciones, participantes, permisos, exportaciones, IndexedDB y SQLite; no construir otro motor. Separar entidades de observaciones, asignaciones de corrección, importaciones masivas y manifiestos de sincronización. El endpoint actual de corrección basado en `records.write` necesita validación específica de destinatario, estado y versión.

## 10. Pruebas mínimas
1. Formulario 350+ preguntas con paginación manual, REPEAT, matriz, condicionales y adjuntos.
2. Borrador editable; enviado y aprobado bloqueados; devuelto editable solo por gestor asignado.
3. Devolución a capturista con datos locales: solo diferencias; reasignación a tablet nueva: respuestas y archivos íntegros.
4. Conflictos entre tablets sin sobrescritura.
5. Excel de 1.000 filas con errores y reintentos idempotentes.
6. Observaciones visibles y navegación a pregunta/ítem REPEAT.
7. Exportación de respuestas sin ninguna observación y sin duplicados; exportación de calidad independiente.

## 11. Implementación por fases
1. Modelo de datos y migraciones.
2. Permisos por registro y devolución individual.
3. Observaciones por pregunta y exportaciones limpias.
4. Importador masivo de devoluciones.
5. Sincronización bidireccional incremental, adjuntos y reasignación offline.
6. Pruebas API, web, móvil, escritorio y UAT; despliegue controlado.

## 12. Estado verificado
Existen servicios de corrección, revisión, reapertura, asignaciones y partes de cola offline. **No se declara implementada** la combinación completa de observaciones estructuradas, exportaciones separadas certificadas, devoluciones masivas, reasignación y sincronización diferencial entre tablets.
