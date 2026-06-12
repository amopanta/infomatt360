# InfoMatt360 - Modelo de Datos Maestro

Estado: version inicial

## 1. Objetivo
Definir el modelo de datos base de InfoMatt360 para soportar administracion nacional, proyectos separados, formularios dinamicos, participantes, registros, evidencias, sincronizacion, integraciones, reportes, auditoria e IA.

## 2. Principio central
El participante, el proyecto y el formulario son ejes principales del sistema.

Un registro puede nacer desde web, Android, escritorio, carga masiva, API o integracion externa, pero debe reflejarse como parte de una misma historia operativa.

## 3. Esquema maestro nacional

### tenants
Representa organizaciones o espacios superiores.

Campos sugeridos:
- id
- nombre
- estado
- dominio
- fecha_creacion

### projects
Representa proyectos operativos independientes.

Campos sugeridos:
- id
- tenant_id
- nombre
- descripcion
- estado
- estrategia_datos
- storage_profile_id
- mail_profile_id
- fecha_creacion

### national_admin_users
Usuarios con permisos nacionales o globales.

## 4. Identidad y acceso

### users
Usuario unico para web, Android y escritorio.

Campos sugeridos:
- id
- nombre
- documento
- correo
- telefono
- password_hash
- estado
- ultimo_acceso

### roles
Roles configurables por proyecto.

### permissions
Permisos por modulo, accion, proyecto, formulario, registro o territorio.

### user_project_assignments
Relacion entre usuarios y proyectos.

## 5. Formularios

### forms
Definicion general del formulario.

Campos sugeridos:
- id
- project_id
- nombre
- descripcion
- estado
- version_actual
- tipo
- creado_por

### form_versions
Versiones publicadas o en borrador.

### form_fields
Campos del formulario.

Debe soportar:
- texto
- numero
- fecha
- seleccion
- multiple seleccion
- grillas
- subformularios
- firma
- foto
- video
- archivo
- GPS
- QR
- OCR
- calculados

### form_rules
Reglas de obligatoriedad, saltos, validaciones, visibilidad y consistencia.

## 6. Participantes y registros

### participants
Entidad central para personas, hogares, beneficiarios, casos o unidades territoriales.

Campos sugeridos:
- id
- project_id
- identificador
- tipo
- nombres
- documento
- metadata
- estado

### records
Respuesta o registro asociado a formulario y participante.

Campos sugeridos:
- id
- project_id
- form_id
- form_version_id
- participant_id
- estado
- origen
- payload_json
- hash_contenido
- creado_por
- actualizado_por

### record_history
Historial de cambios del registro.

### workflow_events
Eventos de flujo: enviado, devuelto, corregido, aprobado, rechazado, anulado, sincronizado.

## 7. Evidencias y archivos

### file_assets
Archivos, imagenes, videos, firmas, PDF, OCR y documentos.

Campos sugeridos:
- id
- project_id
- participant_id
- record_id
- tipo
- nombre_original
- ruta_storage
- proveedor_storage
- mime_type
- peso_bytes
- hash_archivo
- metadata_ocr
- creado_por

### storage_profiles
Configuracion de almacenamiento local, MinIO, S3, Google Drive u otros.

## 8. Correo y notificaciones

### mail_profiles
Configuracion SMTP, IMAP, OAuth o proveedor externo por proyecto.

### internal_messages
Bandeja interna.

### notifications
Notificaciones por correo, bandeja interna o canal externo.

## 9. Sincronizacion

### sync_sessions
Sesiones de sincronizacion web, Android, escritorio o integracion.

### sync_queue
Cola de datos pendientes.

### sync_conflicts
Conflictos detectados.

## 10. Integraciones externas

### external_connections
Conexiones a APIs, Excel, CSV, JSON, bases externas o sistemas externos.

### external_field_maps
Diccionario de campos externos contra campos internos.

### external_filters
Filtros no-code para seleccionar registros.

### imported_tables
Tablas internas generadas desde fuentes externas.

### mirror_jobs
Base espejo y sincronizaciones hacia bases externas.

## 11. Reportes

### reports
Definicion de reportes dinamicos.

### report_queries
Configuracion no-code de fuente, campos, filtros, agrupaciones y calculos.

### report_public_links
Enlaces publicados con permisos, vencimiento y descarga.

### report_exports
Historial de exportaciones.

## 12. IA

### ai_validations
Resultados de validacion automatica.

### ai_reports
Analisis cualitativo, cuantitativo y reportes ejecutivos.

### ocr_results
Lecturas OCR y metadatos extraidos de documentos.

## 13. Mesa de ayuda

### support_tickets
Tickets por usuario, proyecto, modulo, dispositivo o registro.

### support_ticket_events
Historial de atencion.

## 14. Auditoria

### audit_log
Toda accion critica debe registrarse.

Debe guardar:
- usuario
- proyecto
- modulo
- accion
- entidad
- antes
- despues
- fecha
- ip
- dispositivo

## 15. Estados base

Registros:
- borrador
- enviado
- en_revision
- devuelto
- corregido
- aprobado
- rechazado
- anulado
- sincronizado

Proyectos:
- activo
- suspendido
- cerrado

Usuarios:
- activo
- bloqueado
- suspendido

## 16. Reglas de integridad

- Cada registro debe pertenecer a un proyecto.
- Cada archivo debe estar asociado a proyecto y origen.
- Cada cambio debe dejar auditoria.
- Cada sincronizacion debe registrar resultado.
- Cada reporte publicado debe respetar permisos.
- Cada tabla importada debe tener diccionario de datos.
