# Mejoras de formularios y agenda interna (16 de octubre de 2026)

## Alcance publicado

- El constructor puede sugerir preguntas editables a partir del texto de un PDF de hasta 5 MB y 20 páginas. No crea ni publica un formulario por sí mismo. Los PDF escaneados requieren OCR previo.
- El constructor ofrece sugerencias de preguntas con el proveedor definido mediante `AI_AUDIT_PROVIDER`, `AI_AUDIT_API_KEY`, `AI_AUDIT_MODEL` y, si aplica, `AI_AUDIT_BASE_URL`. Envía solo la descripción escrita por el usuario y exige `builder.write`. Las sugerencias se revisan antes de agregarlas.
- Los campos `LOOKUP` y `REFERENCE` pueden consultar registros de otra plantilla cuando se configura la plantilla vinculada y el campo usado como etiqueta.
- Los campos de texto, teléfono y documento pueden precargarse desde datos del participante. Un valor ya diligenciado conserva prioridad.
- Los borradores locales se separan por plantilla y participante. Antes del envío se muestra un resumen para confirmar la respuesta.
- La lista de participantes muestra una agenda de seguimientos con fecha, participante y actividad. Los seguimientos se crean desde el detalle del participante con responsable y fecha; se reutiliza el módulo de casos existente. La API filtra por proyecto y visibilidad del participante.

## Configuración y límites

El VPS no tenía `AI_AUDIT_PROVIDER` ni `AI_AUDIT_API_KEY` configurados al desplegar esta versión. La opción de IA devuelve un mensaje de configuración pendiente hasta que un administrador incorpore la clave en el entorno del backend y reinicie el servicio. No se debe copiar la clave al frontend ni a GitHub.

La agenda muestra seguimientos fechados del proyecto. Esta versión no gestiona cupos, disponibilidad ni conflictos entre turnos. Los borradores locales permanecen en el dispositivo y navegador donde se crearon; no sustituyen la sincronización del backend.

## Verificación

- Compilación de producción del frontend: correcta.
- Pruebas de precarga del participante: 2 correctas.
- Prueba de extracción de preguntas de PDF: 1 correcta.
- Despliegue del commit `8ec54b6` en el VPS: backend 1 y 2 saludables; sitio público responde HTTP 200.
- Rutas nuevas visibles en el esquema de la API: `/api/v1/builder/assist/pdf-questions`, `/api/v1/builder/assist/ai-questions` y `/api/v1/cases/project/{project_id}/schedule`.

Las pruebas de captura con usuarios reales, respuesta del proveedor de IA y reserva concurrente de turnos quedan pendientes de credenciales y configuración operativa.
