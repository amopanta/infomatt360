import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { hasAnyCurrentProjectPermission, PROJECT_KEY } from '../auth/session';
import { fetchMyFormSummary, type MyFormSummary } from '../builder/myFormsApi';
import { fetchDashboard } from './api';
import type { DashboardSummary } from './api';
import { useI18n } from '../../i18n';

export function DashboardApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [myAssignments, setMyAssignments] = useState<MyFormSummary | null>(null);
  const [message, setMessage] = useState(t('dashboard.loading'));
  useEffect(() => { fetchDashboard(projectId).then((result) => { setSummary(result); setMessage(''); }).catch((error: Error) => setMessage(error.message)); }, [projectId]);
  useEffect(() => { if (projectId && hasAnyCurrentProjectPermission(['records.write'])) void fetchMyFormSummary(projectId).then(setMyAssignments).catch(() => setMyAssignments(null)); }, [projectId]);
  const formCount = myAssignments?.form_count ?? 0;
  return <AppShell title={t('ux.nav.home')}><main className="dashboard-shell"><QuickActions />{message ? <p role="status">{message}</p> : null}{summary ? <><section className="dashboard-cards"><MetricCard label={t('dashboard.myForms')} value={formCount} detail={`${(myAssignments?.assignment_count ?? 0)} ${t('dashboard.participantsAssigned')}`} href="/my-forms" /><MetricCard label={t('dashboard.records')} value={summary.records_total} detail={statusSummary(summary.records_by_status)} href="/records" /><MetricCard label={t('dashboard.activeUsers')} value={summary.users_total} detail={t('dashboard.assignedToProject')} href="/admin/users" /><MetricCard label={t('dashboard.evidence')} value={summary.files_total} detail={formatBytes(t, summary.storage_bytes)} href="/records" /></section>{(myAssignments?.assignment_count ?? 0) > 0 && <section className="dashboard-panel"><header><div><h2>{t('dashboard.myAssignments')}</h2><p>{t('dashboard.openCapture')}</p></div><a href="/my-forms">{t('app.viewAll')}</a></header><div className="dashboard-activity">{(myAssignments?.pending ?? []).map((item) => <a key={`${item.template_id}:${item.participant_id}`} href={`/runtime/${item.template_id}?participantId=${item.participant_id}`}><span><strong>{item.template_name}</strong><small>{item.participant_name} · {item.document_id || t('dashboard.noDocument')}</small></span><span>{t('dashboard.fillIn')}</span></a>)}</div></section>}<section className="dashboard-panel"><header><div><h2>{t('dashboard.recentActivity')}</h2><p>{t('dashboard.recentDescription')}</p></div><a href="/records">{t('app.viewAll')}</a></header>{summary.recent_records.length ? <div className="dashboard-activity">{summary.recent_records.map((record) => <a key={record.id} href={`/records/${record.template_id}`}><span><strong>{record.template_name}</strong><small>{new Date(record.created_at).toLocaleString()}</small></span><em className={`record-status ${record.status}`}>{record.status}</em></a>)}</div> : <p>{t('dashboard.noActivity')}</p>}</section></> : null}</main></AppShell>;
}

/** Accesos grandes a las tareas principales, filtrados por permisos, para que
 * una persona sin capacitación encuentre por dónde empezar sin usar el menú. */
function QuickActions() {
  const { t } = useI18n();
  const actions = [
    { href: '/builder/new', emoji: '✏️', title: 'ux.home.createTitle', text: 'ux.home.createText', permissions: ['builder.write'] },
    { href: '/my-forms', emoji: '📝', title: 'ux.home.fillTitle', text: 'ux.home.fillText', permissions: ['records.write'] },
    { href: '/records', emoji: '📊', title: 'ux.home.dataTitle', text: 'ux.home.dataText', permissions: [] as string[] },
    { href: '/records', emoji: '✅', title: 'ux.home.reviewTitle', text: 'ux.home.reviewText', permissions: ['records.approve', 'records.review'] },
  ].filter((action) => !action.permissions.length || hasAnyCurrentProjectPermission(action.permissions));
  return (
    <section className="home-quick" aria-labelledby="home-quick-title">
      <h2 id="home-quick-title">{t('ux.home.greeting')}</h2>
      <div className="home-quick-grid">
        {actions.map((action) => (
          <a key={action.title} className="home-quick-card" href={action.href}>
            <span className="home-quick-emoji" aria-hidden="true">{action.emoji}</span>
            <strong>{t(action.title)}</strong>
            <small>{t(action.text)}</small>
          </a>
        ))}
      </div>
    </section>
  );
}

function MetricCard({ label, value, detail, href }: { label: string; value: number; detail: string; href: string }) {
  return <a className="dashboard-metric" href={href}><span>{label}</span><strong>{value.toLocaleString()}</strong><small>{detail}</small></a>;
}

function statusSummary(values: Record<string, number>): string {
  const parts = Object.entries(values).map(([status, count]) => `${count} ${status}`);
  return parts.join(' · ') || '';
}

function formatBytes(t: (key: string, params?: Record<string, string | number>) => string, value: number): string {
  if (value < 1024) return t('format.bytes', { value: String(value) }) + ' ' + t('dashboard.stored');
  if (value < 1024 ** 2) return t('format.kilobytes', { value: (value / 1024).toFixed(1) }) + ' ' + t('dashboard.stored');
  return t('format.megabytes', { value: (value / 1024 ** 2).toFixed(1) }) + ' ' + t('dashboard.stored');
}
