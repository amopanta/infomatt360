# 109. Constructor visual de actas

## Qué cierra esto

El ítem #4 de `docs/96_AUDITORIA_TRAZABILIDAD_REQUERIMIENTOS_V1.md`:

> Constructor visual de actas/documentos (arrastrar logos, encabezados, tablas, firmas) (§7, §16) — FALTA. `ActaTemplateCreate.html_template` es un campo de texto Jinja2 crudo; no existe UI de diseño visual en el frontend.

La investigación previa a implementar confirmó que el vacío era más grande de lo que dice el propio texto de la auditoría: **actas no tenía ningún frontend en absoluto** — ni siquiera un editor de HTML crudo. Solo existía el backend (`ActaTemplate` con un campo `html_template` de texto Jinja2, render vía `xhtml2pdf`), sin ningún consumidor en `frontend/src`.

**Alcance acordado con el usuario (AskUserQuestion):**
1. El bloque "tabla" se enlaza a los valores de un **registro Runtime real** — el acta se genera a partir de una captura existente, no de entrada manual.
2. El branding de organización (logo/colores) se inyecta **automáticamente** en el bloque logo, sin subida manual.
3. Primera versión con exactamente los **4 bloques que nombra docs/96**: logo, encabezado, tabla, firma. Sin firma electrónica (solo línea + etiqueta para firma física), sin generación masiva (docs/96 #5, item aparte) y sin constructor de reportes/tableros (docs/96 #6, item aparte).

## Diseño

### Dos caminos conviven en la misma tabla

`ActaTemplate` (`backend/app/models/acta.py`) ganó dos columnas nuevas (`layout_json`, `template_id`) y `html_template` pasó a ser nullable. Una fila nunca mezcla los dos caminos — se valida en el servicio, no en la base de datos:

- **Legado**: `html_template` no nulo, `layout_json`/`template_id` nulos. Sigue exactamente igual que antes (`POST /acta-templates/`, `PUT /{id}`, `POST /{id}/render` con un `data: dict[str, str]` arbitrario) — nunca tuvo UI y sigue sin tenerla; queda como vía de escape para uso avanzado directo por API.
- **Constructor visual**: `layout_json` no nulo, `template_id` (el `BuilderTemplate` para el que fue diseñada) también no nulo. Nuevos endpoints `POST /acta-templates/layout`, `PUT /{id}/layout`, `POST /{id}/render-from-record`.

### Bloques estructurados, no HTML libre

`ActaLayout.blocks` es una lista de bloques discriminados por `type` (`backend/app/schemas/acta.py`): `logo` (alineación, sin URL propia), `header` (texto que puede contener tokens `{{campo}}`, resueltos contra el registro al momento de generar), `table` (lista de `field_names` a incluir, renderizados como filas Campo/Valor), `signature` (solo una etiqueta de texto — línea física, no firma electrónica). Se persiste como JSON en `layout_json`, siguiendo la misma convención ya madura del repo para datos estructurados (`BuilderTemplate.theme_json`, `BuilderComponent.config_json`/`rules_json`) — no se creó una tabla relacional nueva.

`render_html_from_blocks` (`backend/app/services/acta_service.py`) resuelve cada bloque contra datos reales: carga el `RuntimeRecord` (rechaza con 422 explícito si no pertenece al `template_id` de la plantilla de acta), sus `RuntimeRecordValue`, las etiquetas humanas desde `BuilderComponent.label` (no el nombre técnico del campo), y el branding de la organización del proyecto vía `organization_service.get_branding` (si no hay organización o no hay logo configurado, el bloque logo se omite con gracia — comentario HTML, no una imagen rota). El resultado se pasa por el mismo `pisa.CreatePDF` (xhtml2pdf) que ya usaba el camino legado — se factorizó a `_html_to_pdf_bytes`, compartida entre ambos caminos.

### Migración

`backend/alembic/versions/0066_acta_layout_blocks.py` — primera migración de este repo que vuelve nullable una columna ya existente (`html_template`), usando `op.batch_alter_table` (SQLite no soporta `ALTER COLUMN` directo). Las dos columnas nuevas se agregan con el patrón `op.add_column` + guarda de idempotencia ya establecido en el repo.

### Frontend

Nuevo módulo `frontend/src/modules/acta/`: `ActaListApp` (lista de plantillas del proyecto), `ActaBuilderApp` (constructor: elige el formulario destino, arma los bloques, guarda, y tiene un botón "Generar PDF de prueba" que sirve a la vez de vista previa real y de flujo de producción — no hay un motor de preview HTML/CSS separado), `ActaCanvas` (reordenamiento por arrastre, reusando el mismo patrón de drag HTML5 nativo ya probado en `BuilderCanvas.tsx` del constructor de formularios — no se reusó su código, que es específico de validación de campos, solo el patrón de interacción), `ActaPalette` (clic para agregar un bloque). Nueva entrada "Actas" en el menú lateral, ruta `/acta`, protegida por `builder.write` (mismo permiso que ya exige el constructor de formularios).

Se agregó `GenerateActaPanel` a `frontend/src/modules/records/RecordsApp.tsx` en los dos lugares donde se muestra el detalle de un registro (la fila expandida de la tabla y `DeepLinkedRecordCard`, usado por los enlaces de corrección vía WhatsApp): lista las plantillas de acta diseñadas para el formulario de ese registro y genera el PDF con un clic, cerrando el ciclo real "registro capturado → documento oficial".

## Pruebas

`backend/tests/test_acta.py` (5 pruebas nuevas, sobre las 4 ya existentes del camino legado, que siguen pasando sin cambios): creación/listado del constructor visual exige `builder.write`; el PDF generado contiene el valor real del registro, el encabezado con el token resuelto, las etiquetas humanas de la tabla (no el nombre técnico) y la línea de firma, y el `<img>` del logo referencia la URL real de branding cuando existe; sin organización/branding vinculados el HTML no contiene ningún `<img>` roto; un registro de un formulario distinto al de la plantilla de acta se rechaza con 422; una plantilla legado no se puede editar con el endpoint del constructor visual.

Durante la implementación se detectó y corrigió un bug propio: la primera versión del schema `ActaTemplateRead` heredaba de `ActaTemplateCreate`, cuyo `html_template` es obligatorio — construir la respuesta para una fila del constructor visual (con `html_template=None`) habría fallado la validación de Pydantic. Se corrigió declarando `ActaTemplateRead` de forma independiente, con todos los campos opcionales salvo los que son comunes a ambos caminos.

`frontend/src/modules/acta/blockOrder.test.ts` (8 pruebas nuevas): `reorderBlocks` (mover al final, al principio, un solo bloque, índices iguales o fuera de rango son no-op) y `extractTokens` (extrae los nombres de campo de un texto con varios tokens, lista vacía sin tokens, ignora llaves vacías o mal formadas). `routeConfig.test.ts` ganó 2 casos para la ruta `/acta`. No se agregaron pruebas de renderizado de componentes React — consistente con el resto del repo, que no usa React Testing Library; esos flujos quedan cubiertos por la verificación en vivo.

Suite completa tras el cambio: backend 371/371 (356 previos + 5 nuevos, mismos 5 errores preexistentes ya documentados por el bloqueo de `.pytest_cache` en Windows), frontend 56/56 (48 previos + 8 nuevos), `tsc --noEmit` y `npm run build` limpios.

## Verificación en vivo

Contra el backend y frontend reales de la demo, con `admin@infomatt360.demo`, tras aplicar la migración `alembic upgrade head` sobre la base real:

- Se creó una plantilla de acta ligada a "Caracterizacion demo" con los 4 bloques (logo centrado, encabezado `"Acta de {{nombre}}"` insertado con el helper de tokens haciendo clic en el campo real —no escribiendo el texto a mano—, tabla con "Nombre del hogar"/"Numero de integrantes" seleccionados mostrando sus etiquetas humanas, firma "Firma del coordinador"). Se guardó correctamente.
- Se generó un PDF real contra el registro demo "Hogar Norte": se extrajo el texto del PDF (`pypdf`) y se confirmó que contiene exactamente `"Acta de Hogar Norte"` (token resuelto), la tabla con las etiquetas y valores correctos, y la línea de firma — sin ningún `<img>` roto pese a que el proyecto demo no tiene organización/branding configurados.
- Se confirmó el panel "Generar acta" en Registros, tanto en la fila expandida como en el flujo de deep-link (`/records/{template}?recordId=...&campo=...`, el mismo usado por los enlaces de corrección de WhatsApp) — ambos generan el mismo PDF vía el mismo endpoint.
- Se confirmó que el camino legado (`POST /acta-templates/` + `POST /{id}/render` con `ActaRenderRequest{data}`) sigue funcionando igual, vía llamada directa a la API (nunca tuvo UI, así que no hay forma de ejercitarlo desde el frontend).
- La inyección de branding automática se probó de forma aislada (crear organización + branding de prueba vía API) para confirmar que el mecanismo no rompe nada, pero **no se vinculó** al proyecto demo compartido: no existe ningún endpoint para editar `Project.organization_id`, y hacerlo directo en la base de datos habría dejado ese campo del proyecto demo modificado sin una vía limpia de reversión por API. Esa combinación específica (branding real + proyecto real) ya está cubierta con precisión por la prueba de pytest dedicada, que sí crea y descarta sus propios datos de forma aislada.
- El reordenamiento por arrastre en `ActaCanvas` no se ejercitó con una simulación de drag real en el navegador (los gestos de arrastre son difíciles de automatizar de forma confiable) — queda cubierto por las 5 pruebas unitarias de `reorderBlocks` y por ser una reutilización directa del mismo patrón de `BuilderCanvas.tsx`, ya en producción.
- Todos los datos de prueba (2 plantillas de acta, la organización y el branding de prueba) se eliminaron al finalizar; `backend/.env` y `frontend/.env.local` se revirtieron a su estado original.

## Lo que queda fuera de esta sesión

Docs/96 #5 (generación masiva de actas en lote) y #6 (constructor visual de reportes/tableros) son ítems aparte, no incluidos aquí por decisión explícita del usuario.
