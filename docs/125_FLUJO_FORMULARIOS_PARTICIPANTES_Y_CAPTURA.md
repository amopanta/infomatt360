# 125. Formularios, participantes y captura asignada

Actualizado: 2026-10-05. Esta guía cubre el flujo implementado en la web y en la aplicación de escritorio, que usa la misma interfaz publicada.

## Configurar un formulario para un responsable

1. En el proyecto correcto, abre **Formularios → [formulario] → Configuración → Fuente de participantes** con una cuenta que tenga permisos de constructor y administración de usuarios.
2. Selecciona **Cerrado: solo población previamente asignada** cuando el responsable deba trabajar únicamente con participantes existentes. Selecciona el origen: todos, lista seleccionada, grupo, municipio, grupo Pull o formulario anterior.
3. Elige la llave de captura: **Número de documento o cédula** o **Código del participante**. Pulsa **Guardar fuente**.
4. En **Asignaciones por responsable**, elige el usuario del mismo proyecto. Puedes usar **Asignar uno a uno** o **Asignar varios participantes**. La opción masiva permite escoger un grupo completo o subir un `.xlsx`/`.csv` con una sola columna `documento` o `codigo` y una fila por persona. Pulsa **Validar asignación**, revisa nuevos, reasignaciones, ya asignados, protegidos y errores, y después **Confirmar asignación masiva**. Los registros con respuesta o cerrados se conservan. El archivo admite hasta 5000 filas y 5 MB; guarda los documentos como texto en Excel para preservar ceros iniciales.
5. Publica el formulario en **Configuración → Publicación y respuestas**. Un borrador no admite captura.

El responsable con permiso `records.write` encuentra sus asignaciones en **Panel → Mis formularios** o en el menú **Mis formularios** (`/my-forms`). Allí ve el formulario, nombre y documento del participante, estado de la actividad y la acción **Diligenciar** o **Ver respuesta**. El panel **Actividad reciente** muestra registros enviados; no es el catálogo de formularios pendientes.

La API `GET /api/v1/form-assignments/mine/{project_id}` entrega únicamente asignaciones propias, del proyecto autorizado y de formularios publicados. El administrador usa la tabla de asignaciones en la configuración del formulario. La visibilidad territorial y los permisos de proyecto siguen aplicando.

## Captura y respuestas

Al abrir **Diligenciar**, el documento o código identifica al participante asignado. Su información aparece dentro del formulario antes de las preguntas. Al guardar, la respuesta queda vinculada al participante y la actividad pasa a completada. Una actividad ya enviada no admite otra respuesta ordinaria; se consulta la existente y las correcciones siguen el flujo de revisión y reapertura autorizado.

La grilla de **Registros y respuestas** muestra nombre, documento, código y municipio del participante, junto a las respuestas. Admite búsqueda por nombre, documento o código; el CSV incluye estas columnas. Los registros históricos sin relación muestran **Sin participante enlazado**.

## Importar el XLSForm MEAL

En **Importar/Exportar XLSForm**, usa **Validar y comparar XLSForm** antes de importar o reemplazar. El tipo `photo` se importa como `IMAGE`. Las reglas compatibles del archivo MEAL (`today()`, comparaciones entre campos, `string-length(.)` y `selected(...)`) se conservan y ejecutan en Runtime. Las expresiones que sigan sin soporte generan advertencias para revisión. La prueba con `Formulario_KoboToolbox_MEAL.xlsx` adjunto al trabajo del 2026-10-05 no produjo las seis advertencias de lógica observadas anteriormente y reconoció `foto_fachada` como imagen.

Un formulario importado antes de esa corrección conserva su versión anterior. Para aplicarla a ese formulario, usa **Reemplazar**, sube el XLSForm, revisa **Validar y comparar** y confirma el reemplazo. El reemplazo conserva la identidad y los registros históricos del formulario.

## Captura sin conexión: límite vigente

Existe una cola local de sincronización para capturas compatibles, pero la captura **vinculada a participantes asignados** todavía requiere conexión para verificar la asignación y guardar la respuesta. Si falla la red durante este flujo, conserva el formulario abierto y envíalo al recuperar la conexión. El primer inicio de sesión de la aplicación de escritorio también requiere conexión. Véanse `desktop/README.md` y `docs/106`–`107` para el alcance de la cola local.

## Verificación y trazabilidad

- [PR 24](https://github.com/amopanta/infomatt360/pull/24): identidad del participante en grilla, detalle, búsqueda y CSV. `backend/tests/test_runtime_records.py`: 10 pruebas aprobadas.
- [PR 25](https://github.com/amopanta/infomatt360/pull/25): corrección XLSForm MEAL. `backend/tests/test_xlsform_import.py`: 6 pruebas; `frontend/src/modules/runtime/xlsExpression.test.ts`: 3 pruebas aprobadas.
- [PR 26](https://github.com/amopanta/infomatt360/pull/26): **Mis formularios** para responsables. `backend/tests/test_form_assignments_reopening.py`: 3 pruebas aprobadas.
- Tras cada despliegue se comprobó compilación y salud de los dos servicios backend, el frontend y las rutas públicas `/` y `/api/v1/health/` (HTTP 200). Esas comprobaciones no sustituyen una prueba manual autenticada de cada flujo en producción.
