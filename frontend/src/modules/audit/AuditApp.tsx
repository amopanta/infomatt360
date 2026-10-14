import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchAuditLogs } from './api';
import type { AuditLog } from './api';

export function AuditApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [moduleFilter, setModuleFilter] = useState('');
  const [message, setMessage] = useState(t('audit.loading'));

  useEffect(() => {
    fetchAuditLogs({ projectId, module: moduleFilter, limit: 150 })
      .then((items) => {
        setLogs(items);
        setMessage(items.length ? '' : t('audit.noEvents'));
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId, moduleFilter]);

  const modules = useMemo(() => Array.from(new Set(logs.map((log) => log.module))).sort(), [logs]);

  return (
    <AppShell title={t('audit.title')}>
      <main className="audit-shell">
        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('audit.recentEvents')}</h2>
              <p>{t('audit.description')}</p>
            </div>
            <select aria-label={t('audit.filterModule')} value={moduleFilter} onChange={(event) => setModuleFilter(event.target.value)}>
              <option value="">{t('audit.allModules')}</option>
              {modules.map((module) => <option key={module} value={module}>{module}</option>)}
            </select>
          </header>
          {message ? <p role="status">{message}</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('audit.date')}</th>
                  <th>{t('audit.module')}</th>
                  <th>{t('audit.action')}</th>
                  <th>{t('audit.entity')}</th>
                  <th>{t('audit.user')}</th>
                  <th>{t('audit.detail')}</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td>{new Date(log.created_at).toLocaleString()}</td>
                    <td>{log.module}</td>
                    <td><span className="audit-action">{log.action}</span></td>
                    <td>{[log.entity_type, log.entity_id].filter(Boolean).join(' · ') || '—'}</td>
                    <td>{log.user_id || t('audit.system')}</td>
                    <td><AuditDetails log={log} /></td>
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

function AuditDetails({ log }: { log: AuditLog }) {
  const text = log.after_json || log.before_json || log.device_info || log.ip_address || '';
  if (!text) return <>—</>;
  return <code>{text.length > 120 ? `${text.slice(0, 120)}…` : text}</code>;
}
