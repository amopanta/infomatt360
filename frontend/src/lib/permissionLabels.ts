const labels: Record<string, string> = {
  'projects.read': 'Consultar proyectos', 'identity.users.manage': 'Administrar usuarios y permisos',
  'participants.create': 'Crear participantes', 'organizations.manage': 'Administrar organizaciones',
  'organizations.branding.manage': 'Configurar imagen de la organización', 'organizations.tenant_clean': 'Limpiar datos de la organización',
  'backups.manage': 'Administrar copias de seguridad', 'erp.manage': 'Administrar inventario y honorarios',
  'ai.audit.manage': 'Administrar auditoría con IA', 'support.tickets.manage': 'Administrar solicitudes de soporte',
  'storage.manage': 'Administrar almacenamiento', 'mirror.manage': 'Administrar réplicas',
  'records.read': 'Consultar registros', 'records.write': 'Capturar y editar registros',
  'records.link_participant': 'Vincular registros con participantes', 'records.review': 'Revisar registros',
  'records.coordinate': 'Validar como coordinador', 'records.approve': 'Aprobar registros', 'records.void': 'Anular registros',
  'reports.export': 'Exportar informes', 'gis.read': 'Consultar mapas', 'builder.write': 'Diseñar formularios',
  'messages.read': 'Leer mensajes', 'messages.write': 'Escribir mensajes',
  'integrations.api_keys.manage': 'Administrar claves de integración', 'integrations.donor_sync.manage': 'Administrar sincronización con donantes',
};
export const permissionLabel = (permission: string) => labels[permission] ?? permission;
