import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchWhatsAppNotifications } from './whatsappApi';
import type { WhatsAppNotification } from './whatsappApi';

export function WhatsAppApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [notifications, setNotifications] = useState<WhatsAppNotification[]>([]);
  const [statusFilter, setStatusFilter] = useState('');
  const [message, setMessage] = useState(t('admin.whatsapp.loading'));

  function statusLabel(status: string) {
    const labels: Record<string, string> = {
      sent: t('admin.whatsapp.statusSent'),
      failed: t('admin.whatsapp.statusFailed'),
      skipped: t('admin.whatsapp.statusSkipped'),
    };
    return labels[status] ?? status;
  }

  useEffect(() => {
    fetchWhatsAppNotifications(projectId)
      .then((rows) => {
        setNotifications(rows);
        setMessage(rows.length ? '' : t('admin.whatsapp.noNotificationsYet'));
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
    <AppShell title={t('admin.whatsapp.title')}>
      <main className="audit-shell">
        <section className="wa-summary">
          <article><strong>{notifications.length}</strong><span>{t('admin.whatsapp.total')}</span></article>
          <article><strong>{summary.sent}</strong><span>{t('admin.whatsapp.sent')}</span></article>
          <article><strong>{summary.failed}</strong><span>{t('admin.whatsapp.failed')}</span></article>
          <article><strong>{summary.skipped}</strong><span>{t('admin.whatsapp.skipped')}</span></article>
        </section>
        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.whatsapp.notificationsTitle')}</h2>
              <p>{t('admin.whatsapp.notificationsDescription')}</p>
            </div>
            <select aria-label={t('admin.whatsapp.filterStatusAria')} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="">{t('admin.whatsapp.allStatuses')}</option>
              <option value="sent">{t('admin.whatsapp.filterSent')}</option>
              <option value="failed">{t('admin.whatsapp.filterFailed')}</option>
              <option value="skipped">{t('admin.whatsapp.filterSkipped')}</option>
            </select>
          </header>
          {message ? <p role="status">{message}</p> : null}
          {notifications.length && summary.skipped === notifications.length ? (
            <p className="wa-hint">{t('admin.whatsapp.allSkippedHint')}</p>
          ) : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('admin.whatsapp.colDate')}</th>
                  <th>{t('admin.whatsapp.colStatus')}</th>
                  <th>{t('admin.whatsapp.colRecipient')}</th>
                  <th>{t('admin.whatsapp.colRecord')}</th>
                  <th>{t('admin.whatsapp.colMessage')}</th>
                  <th>{t('admin.whatsapp.colError')}</th>
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
