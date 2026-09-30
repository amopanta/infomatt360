# CommCare e InfoMatt360: comparación y primer alcance implementado

Fecha: 29 de septiembre de 2026. La comparación usa la documentación pública de CommCare y la implementación de este repositorio. No representa una certificación de equivalencia entre productos.

| Capacidad | CommCare | InfoMatt360 antes de este cambio | Alcance de este cambio |
|---|---|---|---|
| Formularios móviles y captura sin conexión | Formularios con sincronización posterior | PWA con cola local y reintentos; importación XLSForm | Ya existía; sin modificación |
| Participantes longitudinales | Casos con propiedades persistentes, lista/detalle, referencias entre formularios | Participante con historial unificado por formulario | Casos web por participante, propiedades JSON, estados, responsable, remisión e historial de eventos |
| Avisos programados | Campañas y recordatorios por SMS, correo o IVR | Mensajes internos, WhatsApp opcional, programador para respaldos | Aviso interno en la fecha límite de un caso y al remitirlo |
| Organización territorial | Jerarquía de ubicaciones y acceso por ubicación | Roles por organización/proyecto; departamento y municipio como atributos de participante | Asignación usuario/departamento/municipio y filtro de participantes y respuestas Runtime vinculadas |
| Exportaciones guardadas | Exportaciones guardadas y reportes programados | CSV por formulario, Excel resumen, reportes visuales | Configuración manual/diaria/semanal, instantánea descargable y aviso interno |

## Referencias oficiales de CommCare

- [Descripción general de CommCare](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2363293739)
- [Gestión de casos](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143955170/Case%2BManagement%2BOverview)
- [Roles y permisos](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2143957921)
- [Mensajería](https://dimagi.atlassian.net/wiki/display/commcarepublic/Getting%2BStarted%2Bwith%2BMessaging?showChildren=false)
- [Glosario de ubicaciones y exportaciones](https://dimagi.atlassian.net/wiki/spaces/commcarepublic/pages/2973171721/CommCare%2BA-Z%2BGlossary)

## Uso en InfoMatt360

1. **Casos:** Participantes → abrir participante → Casos y remisiones. Crear caso, asignar responsable y plazo, cambiar estado o remitir. El historial conserva cada cambio. El programador envía aviso interno al llegar el plazo.
2. **Territorios:** Participantes → Acceso territorial (permiso `identity.users.manage`). Una asignación de departamento cubre sus municipios; una de municipio restringe a ese municipio. Sin asignaciones, se conserva acceso por proyecto. El administrador del proyecto conserva vista completa.
3. **Exportaciones:** Reportes → Exportaciones guardadas y programadas (permiso `reports.export`). Se puede exportar el resumen del proyecto o las respuestas CSV de un formulario. Cada ejecución conserva una instantánea en la base de datos (máximo 25 MB) y avisa al destinatario por mensaje interno. El trabajador `worker-scheduler` ejecuta las frecuencias diaria y semanal.

## Límites conocidos y siguientes incrementos

- Los casos nuevos se administran en web. Aún falta sincronizar casos y propiedades para uso sin conexión, precargar propiedades en formularios y soportar relaciones padre/hijo de casos.
- Los avisos nuevos son internos. Envío programado por correo, SMS o IVR requiere adaptación de canales y configuración operativa; el conector WhatsApp existente no se usa automáticamente para estos avisos.
- El alcance territorial usa dos niveles fijos, departamento y municipio. La jerarquía configurable y su aplicación completa a todos los módulos de análisis, GIS, API externa, actas e integraciones aún requieren trabajo. Las respuestas Runtime sin participante vinculado se ocultan a usuarios territorialmente restringidos.
- Las exportaciones programadas generan archivos dentro de la base de datos y mensajes internos; no envían adjuntos por correo. Se conservan las 20 instantáneas más recientes por configuración; falta una política de retención configurable.
- Antes de usar permisos territoriales como barrera de confidencialidad para todo el sistema, completar una auditoría de todas las rutas de lectura y exportación restantes.
