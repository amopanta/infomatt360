import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { Icon } from '../../components/Icon';
import { StatusRibbon, statusLabel } from '../../components/StatusRibbon';
import { currentSessionProjects, hasAnyCurrentProjectPermission, PROJECT_KEY } from '../auth/session';
import { fetchMyFormSummary, type MyFormSummary } from '../builder/myFormsApi';
import { fetchDashboard } from './api';
import type { DashboardSummary } from './api';
import { useI18n } from '../../i18n';

type Translate = (key: string, params?: Record<string, string | number>) => string;

export function DashboardApp() {
  const { t, locale } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const projectName = currentSessionProjects().find((project) => project.id === projectId)?.name ?? '';
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [myAssignments, setMyAssignments] = useState<MyFormSummary | null>(null);
  const [message, setMessage] = useState(t('dashboard.loading'));
  useEffect(() => { fetchDashboard(projectId).then((result) => { setSummary(result); setMessage(''); }).catch((error: Error) => setMessage(error.message)); }, [projectId]);
  useEffect(() => { if (projectId && hasAnyCurrentProjectPermission(['records.write'])) void fetchMyFormSummary(projectId).then(setMyAssignments).catch(() => setMyAssignments(null)); }, [projectId]);
  const today = new Date().toLocaleDateString(locale === 'en' ? 'en' : 'es-CO', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
  return (
    <AppShell title={t('ux.nav.home')}>
      <main className="dashboard-shell">
        <header className="home-day">
          <p>{today}</p>
          <h2>{projectName || t('ux.nav.home')}</h2>
        </header>
        {message ? <p role="status">{message}</p> : null}
        {summary ? <StatusRibbon total={summary.records_total} byStatus={summary.records_by_status} /> : null}
        <QuickActions />
        {summary ? (
          <div className="home-columns">
            <div>
              {(myAssignments?.assignment_count ?? 0) > 0 && (
                <section className="dashboard-panel">
                  <header><div><h2>{t('dashboard.myAssignments')}</h2><p>{t('dashboard.openCapture')}</p></div><a href="/my-forms">{t('app.viewAll')}</a></header>
                  <div className="dashboard-activity">{(myAssignments?.pending ?? []).map((item) => <a key={`${item.template_id}:${item.participant_id}`} href={`/runtime/${item.template_id}?participantId=${item.participant_id}`}><span><strong>{item.template_name}</strong><small>{item.participant_name} · {item.document_id || t('dashboard.noDocument')}</small></span><span className="home-fill">{t('dashboard.fillIn')}</span></a>)}</div>
                </section>
              )}
              <section className="dashboard-panel">
                <header><div><h2>{t('dashboard.recentActivity')}</h2><p>{t('dashboard.recentDescription')}</p></div><a href="/records">{t('app.viewAll')}</a></header>
                {summary.recent_records.length ? (
                  <div className="dashboard-activity">
                    {summary.recent_records.map((record) => (
                      <a key={record.id} href={`/records/${record.template_id}`}>
                        <time dateTime={record.created_at}>{formatWhen(record.created_at, locale)}</time>
                        <span><strong>{record.template_name}</strong>{record.submitted_by ? <small>{t('dashboard.by', { name: record.submitted_by })}</small> : null}</span>
                        <em className={`record-status status-${record.status}`}>{statusLabel(t, record.status)}</em>
                      </a>
                    ))}
                  </div>
                ) : <p>{t('dashboard.noActivity')}</p>}
              </section>
            </div>
            <aside className="home-facts" aria-labelledby="home-facts-title">
              <h2 id="home-facts-title">{t('dashboard.factsTitle')}</h2>
              <dl>
                {hasAnyCurrentProjectPermission(['records.write']) ? <Fact href="/my-forms" icon="form" label={t('dashboard.myForms')} value={myAssignments?.form_count ?? 0} detail={`${myAssignments?.assignment_count ?? 0} ${t('dashboard.participantsAssigned')}`} /> : null}
                <Fact href="/builder" icon="acta" label={t('dashboard.templates')} value={summary.templates_total} detail={t('dashboard.formsPublished', { published: summary.published_templates, total: summary.templates_total })} />
                <Fact href="/admin/users" icon="users" label={t('dashboard.activeUsers')} value={summary.users_total} detail={t('dashboard.assignedToProject')} />
                <Fact href="/evidence" icon="photo" label={t('dashboard.evidence')} value={summary.files_total} detail={formatBytes(t, summary.storage_bytes)} />
              </dl>
            </aside>
          </div>
        ) : null}
      </main>
    </AppShell>
  );
}

/** Accesos a las tareas principales, filtrados por permisos, para que una
 * persona sin capacitacion encuentre por donde empezar sin usar el menu. */
function QuickActions() {
  const { t } = useI18n();
  const actions = [
    { href: '/builder/new', icon: 'form', title: 'ux.home.createTitle', text: 'ux.home.createText', permissions: ['builder.write'] },
    { href: '/my-forms', icon: 'tablet', title: 'ux.home.fillTitle', text: 'ux.home.fillText', permissions: ['records.write'] },
    { href: '/records', icon: 'records', title: 'ux.home.dataTitle', text: 'ux.home.dataText', permissions: [] as string[] },
    { href: '/records', icon: 'check', title: 'ux.home.reviewTitle', text: 'ux.home.reviewText', permissions: ['records.approve', 'records.review'] },
  ].filter((action) => !action.permissions.length || hasAnyCurrentProjectPermission(action.permissions));
  return (
    <section className="home-quick" aria-labelledby="home-quick-title">
      <h2 id="home-quick-title">{t('ux.home.greeting')}</h2>
      <div className="home-quick-grid">
        {actions.map((action) => (
          <a key={action.title} className="home-quick-card" href={action.href}>
            <span className="home-quick-icon" aria-hidden="true"><Icon name={action.icon} /></span>
            <span><strong>{t(action.title)}</strong><small>{t(action.text)}</small></span>
          </a>
        ))}
      </div>
    </section>
  );
}

function Fact({ href, icon, label, value, detail }: { href: string; icon: string; label: string; value: number; detail: string }) {
  return <a className="home-fact" href={href}><Icon name={icon} /><dt>{label}</dt><dd><strong>{value.toLocaleString()}</strong><small>{detail}</small></dd></a>;
}

function formatWhen(value: string, locale: string): string {
  const date = new Date(value);
  const tag = locale === 'en' ? 'en' : 'es-CO';
  const sameDay = date.toDateString() === new Date().toDateString();
  return sameDay
    ? date.toLocaleTimeString(tag, { hour: '2-digit', minute: '2-digit' })
    : date.toLocaleDateString(tag, { day: 'numeric', month: 'short' });
}

function formatBytes(t: Translate, value: number): string {
  if (value < 1024) return t('format.bytes', { value: String(value) }) + ' ' + t('dashboard.stored');
  if (value < 1024 ** 2) return t('format.kilobytes', { value: (value / 1024).toFixed(1) }) + ' ' + t('dashboard.stored');
  return t('format.megabytes', { value: (value / 1024 ** 2).toFixed(1) }) + ' ' + t('dashboard.stored');
}
