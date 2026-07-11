import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchWhatsAppNotifications } from './whatsappApi';
import type { WhatsAppNotification } from './whatsappApi';

function statusLabel(status: string) {
  const labels: Record<string, string> = {
    sent: 'Enviado',
    failed: 'Fallido',
    skipped: 'Omitido (sin proveedor configurado)',
  };
  return labels[status] ?? status;
}

export function WhatsAppApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [notifications, setNotifications] = useState<WhatsAppNotification[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [message, setMessage] = useState('Cargando notificaciones WhatsApp...');

  useEffect(() => {
    fetchWhatsAppNotifications(projectId)
      .then((rows) => {
        setNotifications(rows);
        setMessage(rows.length ? '' : 'Aún no se ha enviado ninguna notificación WhatsApp en este proyecto.');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const filtered = useMemo(
    () => (statusFilter ? notifications.filter((item) => item.status === statusFilter) : notifications),
    [notifications, statusFilter],
  );

  const summary = useMemo(() => ({
    sent: notifications.filter((item) => item.status === 'sent').length,
    failed: notifications.filter((item) => item.status === 'failed').length,
    skipped: notifications.filter((item) => item.status === 'skipped').length,
  }), [notifications]);

  return (
    <AppShell title="WhatsApp">
      <main className="audit-shell">
        <section className="wa-summary">
          <article><strong>{notifications.length}</strong><span>Total</span></article>
          <article><strong>{summary.sent}</strong><span>Enviados</span></article>
          <article><strong>{summary.failed}</strong><span>Fallidos</span></article>
          <article><strong>{summary.skipped}</strong><span>Omitidos</span></article>
        </section>
        <section className="audit-panel">
          <header>
            <div>
              <h2>Notificaciones de rechazo/devolución por WhatsApp</h2>
              <p>Historial de envíos disparados al rechazar o devolver un registro para corrección (ver docs/85).</p>
            </div>
            <select aria-label="Filtrar estado" value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">Todos los estados</option>
              <option value="sent">Enviado</option>
              <option value="failed">Fallido</option>
              <option value="skipped">Omitido</option>
            </select>
          </header>
          {message ? <p role="status">{message}</p> : null}
          {notifications.length && summary.skipped === notifications.length ? (
            <p className="wa-hint">Todas las notificaciones quedaron "omitidas" porque este servidor no tiene un proveedor de WhatsApp (WAHA) configurado. Ver docs/85_WHATSAPP_WAHA_NOTIFICACIONES.md para activarlo.</p>
          ) : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Fecha</th>
                  <th>Estado</th>
                  <th>Destinatario</th>
                  <th>Registro</th>
                  <th>Mensaje</th>
                  <th>Error</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((item) => (
                  <tr key={item.id}>
                    <td>{new Date(item.created_at).toLocaleString()}</td>
                    <td><span className={`wa-status ${item.status}`}>{statusLabel(item.status)}</span></td>
                    <td>{item.recipient_phone}{item.recipient_user_id ? <><br /><small>{item.recipient_user_id}</small></> : null}</td>
                    <td>{item.reference_record_id ?? '—'}</td>
                    <td><code>{item.message.length > 140 ? `${item.message.slice(0, 140)}…` : item.message}</code></td>
                    <td>{item.error ? <code>{item.error.length > 120 ? `${item.error.slice(0, 120)}…` : item.error}</code> : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
