# Catalogo de permisos

Este documento define los permisos canonicos de InfoMatt360. El backend debe
usar `app.core.permissions` como fuente principal para evitar textos duplicados
o permisos escritos de forma diferente.

## Regla general

- El backend es la fuente de verdad: ninguna pantalla debe confiar solo en el
  ocultamiento visual del frontend.
- El frontend usa los permisos de la sesion para filtrar menus, proteger rutas y
  mejorar la experiencia del usuario.
- Los permisos se asignan por proyecto mediante roles/asignaciones.
- Los permisos nuevos deben agregarse primero al catalogo central y luego a
  seeders, pruebas y documentacion.

## Permisos canonicos actuales

| Permiso | Uso principal |
| --- | --- |
| `projects.read` | Leer informacion basica del proyecto asignado. |
| `identity.users.manage` | Administrar usuarios del proyecto: listar usuarios, corregir correo, reiniciar password y reiniciar MFA. |
| `records.read` | Consultar registros capturados. |
| `records.write` | Crear o sincronizar registros, incluyendo cargas masivas por API key. |
| `records.review` | Revisar registros dentro de un flujo operativo. |
| `records.coordinate` | Coordinar registros o etapas intermedias del flujo. |
| `records.approve` | Aprobar registros o etapas finales del flujo. |
| `reports.export` | Exportar reportes. |
| `gis.read` | Consultar vistas de mapas/GIS. |
| `builder.write` | Crear o editar formularios y estructuras del Builder. |
| `messages.read` | Leer mensajes/notificaciones del proyecto. |
| `messages.write` | Crear mensajes/notificaciones del proyecto. |
| `integrations.api_keys.manage` | Crear, revocar y administrar API keys de integracion. |
| `organizations.manage` | Crear y listar organizaciones (tenants logicos) y asociarlas a proyectos. |
| `organizations.branding.manage` | Configurar marca blanca (logo, colores, eslogan) de una organizacion. |
| `backups.manage` | Ejecutar y consultar respaldos de base de datos desde la web. |
| `erp.manage` | Administrar inventario, configuracion ERP por plantilla y honorarios del motor contable headless. |
| `integrations.donor_sync.manage` | Configurar fuentes externas (ActivityInfo/TolaData u otras), mapeos de campos y consultar el historial de envios. |
| `ai.audit.manage` | Configurar la auditoria semantica con IA por plantilla (campo a analizar, modo de rechazo) y disparar reanalisis manual. |

## Grupos operativos actuales

| Grupo en codigo | Permisos incluidos | Donde se usa |
| --- | --- | --- |
| `BULK_ADMIN_PERMISSIONS` | `integrations.api_keys.manage`, `records.write` | Panel admin para seguimiento de lotes bulk. |
| `METRICS_VIEW_PERMISSIONS` | `identity.users.manage`, `integrations.api_keys.manage`, `records.approve`, `records.write` | Endpoint y panel de metricas operativas. |

## Permisos historicos

`users.admin` puede aparecer en documentacion o datos antiguos como referencia
historica. Para nuevos desarrollos debe usarse `identity.users.manage`.

## Checklist para agregar un permiso

1. Agregar la constante en `backend/app/core/permissions.py`.
2. Usar la constante en endpoints, servicios o dependencias.
3. Agregar el permiso al seeder demo si debe estar disponible en la demo.
4. Agregar o ajustar pruebas.
5. Documentar el permiso en este archivo.
6. Si afecta UX, mapearlo en el frontend para menu/ruta/panel correspondiente.
