/** API timestamps without an offset are UTC; render operational dates in Colombia. */
export function formatOperationalDate(value?: string | null): string {
  if (!value) return '—';
  const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(value) ? value : `${value}Z`;
  const date = new Date(normalized);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString('es-CO', { timeZone: 'America/Bogota', hour12: true });
}

const labels: Record<string, string> = {
  active: 'Activo', inactive: 'Inactivo', suspended: 'Suspendido', blocked: 'Bloqueado',
  person: 'Persona', draft: 'Borrador', submitted: 'Enviado', under_review: 'En revisión',
  tech_approved: 'Aprobado técnico', coordinator_approved: 'Aprobado coordinación',
  returned: 'Devuelto', corrected: 'Corregido', approved: 'Aprobado', rejected: 'Rechazado',
  cancelled: 'Cancelado', archived: 'Archivado', synced: 'Sincronizado', voided: 'Anulado',
  reversed: 'Revertido', published: 'Publicado', accrued: 'Causado', paid: 'Pagado', open: 'Abierto',
  in_progress: 'En seguimiento', referred: 'Remitido', closed: 'Cerrado',
  start_review: 'Iniciar revisión', approve: 'Aprobar', return: 'Devolver', reject: 'Rechazar',
  entrega_aprobada: 'Entrega aprobada', alta_inicial: 'Inventario inicial',
};
export const operationalStatusLabel = (value?: string | null): string => value ? labels[value] ?? value : '—';
