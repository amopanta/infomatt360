import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { authorizationHeader, hasAnyCurrentProjectPermission, PROJECT_KEY } from '../auth/session';
import { navigateTo } from '../../routeConfig';
import { fetchProjectTemplates } from '../records/api';
import { RecordTable } from '../records/RecordsApp';
import type { TemplateSummary } from '../records/api';
import type { RuntimeTemplate } from '../runtime/types';
import { createPublicLink, fetchPublicLinks } from '../admin/publicLinksApi';
import type { PublicFormLink } from '../admin/publicLinksApi';
import { deleteTemplate, duplicateTemplate, fetchTemplateDetail, setTemplateSchedule, setTemplateStatus, updateTemplateProperties } from './api';
import { CollectionPanel } from './CollectionPanel';
import { ParticipantSourcePanel } from './ParticipantSourcePanel';
import { BulkPullPanel, FormLookupPanel } from './FormLookupPanel';
import { exportXlsform, listFormVersions } from '../admin/xlsformApi';
import { useI18n } from '../../i18n';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type DetailTab = 'resumen' | 'formulario' | 'datos' | 'configuracion';

function displayDate(value?: string | null) {
  if (!value) return '—';
  const zoned = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  return new Date(zoned).toLocaleString('es-CO', { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });
}

function publicationLabel(template: TemplateSummary, t: (key: string) => string) {
  const labels: Record<string, string> = {
    accepting: t('builder.forms.statusAccepting'), scheduled: t('builder.forms.statusScheduled'), closed: t('builder.forms.statusClosed'),
    paused: t('builder.forms.statusPausedLabel'), archived: t('builder.forms.statusArchivedLabel'), draft: t('builder.forms.statusDraftLabel'),
  };
  return labels[template.availability || template.status] || template.status;
}

function statusClass(template: TemplateSummary) {
  return template.availability || template.status;
}

function localInputDate(value?: string | null) {
  if (!value) return '';
  const zoned = /(?:Z|[+-]\d\d:\d\d)$/.test(value) ? value : `${value}Z`;
  const date = new Date(zoned);
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60000);
  return local.toISOString().slice(0, 16);
}

export function FormsApp() {
  const templateId = window.location.pathname.match(/^\/builder\/form\/([^/]+)$/)?.[1];
  if (templateId) return <FormDetail templateId={templateId} />;
  if (window.location.pathname === '/builder/pull') return <PullAssignments />;
  return <FormList />;
}

function PullAssignments() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [message, setMessage] = useState(t('builder.forms.loadingForms'));
  useEffect(() => {
    if (!projectId) { setMessage(t('builder.forms.selectProjectPull')); return; }
    fetchProjectTemplates(projectId).then((rows) => { setTemplates(rows); setMessage(''); }).catch((error: Error) => setMessage(error.message));
  }, [projectId]);
  return <AppShell title={t('builder.forms.pullGroupsTitle')}><main className="forms-home">
    <header className="forms-home-head"><div><h1>{t('builder.forms.pullGroupsTitle')}</h1><p>{t('builder.forms.pullGroupsDesc')}</p></div><a className="forms-secondary-link" href="/builder">{t('builder.forms.backToForms')}</a></header>
    {message && <p role="status" className="forms-feedback">{message}</p>}
    {!message && (templates.length ? <BulkPullPanel projectId={projectId} forms={templates} /> : <section className="forms-empty"><h2>{t('builder.forms.noFormsAvailable')}</h2><p>{t('builder.forms.createFormBeforePull')}</p></section>)}
  </main></AppShell>;
}

function FormList() {
  const { t } = useI18n();
  const view = window.location.pathname.split('/')[2] || 'all';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [filter, setFilter] = useState('');
  const [message, setMessage] = useState(t('builder.forms.loadingForms'));

  useEffect(() => {
    if (!projectId) { setMessage(t('builder.forms.selectProjectForms')); return; }
    fetchProjectTemplates(projectId)
      .then((rows) => { setTemplates(rows); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const visible = useMemo(() => templates.filter((template) => {
    const inView = view === 'drafts' ? template.status === 'draft' : view === 'active' ? ['published', 'paused'].includes(template.status) : view === 'archived' ? template.status === 'archived' : true;
    return inView && template.name.toLowerCase().includes(filter.toLowerCase());
  }), [templates, filter, view]);
  const active = templates.filter((template) => ['published', 'paused'].includes(template.status)).length;
  const title = view === 'drafts' ? t('builder.forms.inProgressTitle') : view === 'active' ? t('builder.forms.activeFormsTitle') : view === 'archived' ? t('builder.forms.archivedFormsTitle') : t('builder.forms.allFormsTitle');
  return <AppShell title={t('builder.forms.formsPageTitle')}>
    <main className="forms-home">
      <header className="forms-home-head">
        <div><h1>{title}</h1><p>{view === 'drafts' ? t('builder.forms.draftsDescription') : t('builder.forms.formsDescription')}</p></div>
        {view === 'drafts' && <a className="forms-primary-link" href="/builder/new">{t('builder.forms.newFormButton')}</a>}
      </header>
      <div className="forms-overview"><strong>{t('builder.forms.formsCount', { count: templates.length })}</strong><span>{t('builder.forms.activeOrPausedCount', { count: active })}</span><span>{t('builder.forms.draftsCount', { count: templates.filter((template) => template.status === 'draft').length })}</span><span>{t('builder.forms.archivedCount', { count: templates.filter((template) => template.status === 'archived').length })}</span></div>
      <div className="forms-toolbar"><label>{t('builder.forms.searchForm')}<input value={filter} onChange={(event) => setFilter(event.target.value)} placeholder={t('builder.forms.formNamePlaceholder')} /></label></div>
      {message ? <p role="status" className="forms-feedback">{message}</p> : null}
      {!message && !templates.length ? <section className="forms-empty"><h2>{t('builder.forms.noFormsYet')}</h2><p>{t('builder.forms.startInDrafts')}</p><a className="forms-secondary-link" href="/builder/drafts">{t('builder.forms.goToDrafts')}</a></section> : null}
      {!!visible.length && <div className="forms-table-wrap"><table className="forms-table"><thead><tr><th>{t('builder.forms.columnName')}</th><th>{t('builder.forms.columnStatus')}</th><th>{t('builder.forms.columnOwner')}</th><th>{t('builder.forms.columnLastEdit')}</th><th>{t('builder.forms.columnStart')}</th><th>{t('builder.forms.columnEnd')}</th><th>{t('builder.forms.columnSubmissions')}</th></tr></thead><tbody>
        {visible.map((template) => <tr key={template.id}><td><a className="forms-name" href={`/builder/form/${template.id}`}>{template.name}</a><small>{template.description || t('builder.forms.noDescription')}</small></td><td><span className={`forms-status ${statusClass(template)}`}>{publicationLabel(template, t)}</span></td><td>{template.owner_name || '—'}</td><td>{displayDate(template.updated_at || template.created_at)}</td><td>{displayDate(template.starts_at)}</td><td>{displayDate(template.ends_at)}</td><td><span className="forms-count">{template.submissions_count ?? 0}</span></td></tr>)}
      </tbody></table></div>}
      {!!templates.length && !visible.length && <p className="forms-feedback">{t('builder.forms.noFormsMatchSearch')}</p>}
    </main>
  </AppShell>;
}

function FormDetail({ templateId }: { templateId: string }) {
  const { t } = useI18n();
  const [template, setTemplate] = useState<TemplateSummary | null>(null);
  const [runtime, setRuntime] = useState<RuntimeTemplate | null>(null);
  const [links, setLinks] = useState<PublicFormLink[]>([]);
  const [newPublicUrl, setNewPublicUrl] = useState('');
  const [tab, setTab] = useState<DetailTab>('resumen');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState(t('builder.forms.loadingForm'));
  const [startsAt, setStartsAt] = useState('');
  const [endsAt, setEndsAt] = useState('');
  const [formName, setFormName] = useState('');
  const [formDescription, setFormDescription] = useState('');
  const [versionCount, setVersionCount] = useState(0);
  const [pullCount, setPullCount] = useState(0);
  const [showDelete, setShowDelete] = useState(false);
  const [deleteConfirmation, setDeleteConfirmation] = useState('');
  const canDelete = hasAnyCurrentProjectPermission(['identity.users.manage']);

  const tabLabels: Record<DetailTab, string> = {
    resumen: t('builder.forms.tabSummary'),
    formulario: t('builder.forms.tabForm'),
    datos: t('builder.forms.tabData'),
    configuracion: t('builder.forms.tabConfig'),
  };

  async function fetchRuntimeData(id: string): Promise<RuntimeTemplate> {
    const response = await fetch(`${API_BASE_URL}/runtime/template/${id}`, { headers: authorizationHeader() });
    if (!response.ok) throw new Error(t('builder.forms.runtimeLoadFailed'));
    return response.json();
  }

  useEffect(() => {
    setMessage(t('builder.forms.loadingForm'));
    Promise.all([fetchTemplateDetail(templateId), fetchRuntimeData(templateId), fetchPublicLinks(templateId)])
      .then(([detail, layout, publicLinks]) => { setTemplate(detail); setRuntime(layout); setLinks(publicLinks); setStartsAt(localInputDate(detail.starts_at)); setEndsAt(localInputDate(detail.ends_at)); setFormName(detail.name); setFormDescription(detail.description || ''); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
    void listFormVersions(templateId).then((versions) => setVersionCount(versions.length)).catch(() => setVersionCount(0));
    void fetch(`${API_BASE_URL}/form-lookups/templates/${templateId}`, { headers: authorizationHeader() }).then((response) => response.ok ? response.json() : []).then((items: unknown[]) => setPullCount(items.length)).catch(() => setPullCount(0));
  }, [templateId]);

  const questions = runtime?.pages.flatMap((page) => page.sections.flatMap((section) => section.rows.flatMap((row) => row.columns.flatMap((column) => column.components)))) ?? [];

  async function saveProperties() {
    if (!template) return;
    if (!formName.trim()) { setMessage(t('builder.forms.nameRequired')); return; }
    setBusy(true);
    setMessage('');
    try {
      const updated = await updateTemplateProperties(template.id, { name: formName.trim(), description: formDescription, themeJson: template.theme_json || null });
      setTemplate(updated);
      setMessage(t('builder.forms.nameSaved'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('builder.forms.nameSaveFailed')); }
    finally { setBusy(false); }
  }

  async function changeStatus(next: 'draft' | 'published' | 'paused' | 'archived') {
    if (!template) return;
    setBusy(true);
    setMessage('');
    try {
      const updated = await setTemplateStatus(template.id, next);
      setTemplate(updated);
      const messages: Record<string, string> = { draft: t('builder.forms.statusMsgDraft'), published: t('builder.forms.statusMsgPublished'), paused: t('builder.forms.statusMsgPaused'), archived: t('builder.forms.statusMsgArchived') };
      setMessage(messages[next]);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('builder.forms.statusChangeFailed'));
    } finally { setBusy(false); }
  }

  async function saveSchedule() {
    if (!template) return;
    setBusy(true);
    setMessage('');
    try {
      const start = startsAt ? new Date(startsAt).toISOString() : null;
      const end = endsAt ? new Date(endsAt).toISOString() : null;
      if (start && end && start >= end) throw new Error(t('builder.forms.endBeforeStart'));
      const updated = await setTemplateSchedule(template.id, start, end);
      setTemplate(updated);
      setMessage(t('builder.forms.receptionSaved'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('builder.forms.datesSaveFailed'));
    } finally { setBusy(false); }
  }

  async function makeLink() {
    setBusy(true);
    setMessage('');
    try {
      const issued = await createPublicLink({ templateId });
      setNewPublicUrl(`${window.location.origin}/public-form/${issued.token}`);
      setLinks(await fetchPublicLinks(templateId));
      setMessage(t('builder.forms.publicLinkCreated'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('builder.forms.linkCreateFailed'));
    } finally { setBusy(false); }
  }

  async function copyForm() {
    if (!template) return;
    setBusy(true); setMessage('');
    try { const copy = await duplicateTemplate(template.id); window.location.href = `/builder/form/${copy.id}`; }
    catch (error) { setMessage(error instanceof Error ? error.message : t('builder.forms.duplicateFailed')); setBusy(false); }
  }

  async function removeForm() {
    if (!template || deleteConfirmation !== template.name) return;
    setBusy(true); setMessage('');
    try { await deleteTemplate(template.id, deleteConfirmation); navigateTo('/builder'); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('builder.forms.deleteFailed')); setBusy(false); }
  }

  return <AppShell title={t('builder.forms.tabForm')}><main className="forms-detail">
    <a className="forms-back" href="/builder">{t('builder.forms.allFormsLink')}</a>
    {template && <><header className="forms-detail-head"><div><h1>{template.name}</h1><p>{template.description || t('builder.forms.noDescription')}</p></div><span className={`forms-status ${statusClass(template)}`}>{publicationLabel(template, t)}</span></header>
    <nav className="forms-tabs" aria-label={t('builder.forms.formSectionsAria')}>{(['resumen', 'formulario', 'datos', 'configuracion'] as DetailTab[]).map((item) => <button type="button" key={item} className={tab === item ? 'active' : ''} onClick={() => setTab(item)}>{tabLabels[item]}</button>)}</nav>
    {tab === 'resumen' && <><section className="forms-detail-panel"><h2>{t('builder.forms.adminCenter')}</h2><div className="forms-admin-actions"><a href={`/builder/edit/${template.id}`}>{t('builder.forms.actionEdit')}</a><a href={`/admin/xlsform?replace=${template.id}`}>{t('builder.forms.actionReplace')}</a><a href={`/runtime/${template.id}?preview=1`}>{t('builder.forms.actionPreview')}</a><button type="button" disabled={busy} onClick={() => void copyForm()}>{t('builder.forms.actionDuplicate')}</button><a href={`/admin/xlsform?replace=${template.id}`}>{t('builder.forms.actionVersions')}</a><a href={`/records/${template.id}`}>{t('builder.forms.actionRecords')}</a><button type="button" onClick={() => void exportXlsform(template.id, template.name).catch((error: Error) => setMessage(error.message))}>{t('builder.forms.actionDownload')}</button><button type="button" onClick={() => setTab('configuracion')}>{t('builder.forms.actionPullParticipants')}</button></div></section><div className="forms-detail-grid"><section className="forms-detail-panel"><h2>{t('builder.forms.formInfo')}</h2><p>{template.description || t('builder.forms.addDescriptionHint')}</p><dl className="forms-facts"><div><dt>{t('builder.forms.dtStatus')}</dt><dd><span className={`forms-status ${statusClass(template)}`}>{publicationLabel(template, t)}</span></dd></div><div><dt>{t('builder.forms.dtQuestions')}</dt><dd>{questions.length}</dd></div><div><dt>{t('builder.forms.dtVersions')}</dt><dd>{versionCount}</dd></div><div><dt>{t('builder.forms.dtPullGroups')}</dt><dd>{pullCount}</dd></div><div><dt>{t('builder.forms.dtOwner')}</dt><dd>{template.owner_name || '—'}</dd></div><div><dt>{t('builder.forms.dtLastEdit')}</dt><dd>{displayDate(template.updated_at || template.created_at)}</dd></div><div><dt>{t('builder.forms.dtStartResponses')}</dt><dd>{displayDate(template.starts_at)}</dd></div><div><dt>{t('builder.forms.dtEndResponses')}</dt><dd>{displayDate(template.ends_at)}</dd></div><div><dt>{t('builder.forms.dtSubmissions')}</dt><dd>{template.submissions_count ?? 0}</dd></div><div><dt>{t('builder.forms.dtParticipants')}</dt><dd>{template.participant_source?.mode === 'pull' ? t('builder.forms.pullGroupLabel', { name: template.participant_source.pull_name ?? '' }) : template.participant_source?.mode || t('builder.forms.allParticipants')}</dd></div></dl></section><section className="forms-detail-panel"><h2>{t('builder.forms.receptionControl')}</h2><p>{template.accepting_responses ? t('builder.forms.acceptingResponses') : t('builder.forms.currentStatus', { status: publicationLabel(template, t).toLowerCase() })}</p><button type="button" onClick={() => setTab('configuracion')}>{t('builder.forms.configPublishDates')}</button></section></div></>}
    {tab === 'formulario' && <section className="forms-detail-panel"><div className="forms-panel-head"><div><h2>{t('builder.forms.currentVersion')}</h2><p>{t('builder.forms.versionSummary', { count: questions.length, pages: runtime?.pages.length ?? 0, date: displayDate(template.updated_at) })}</p></div><div className="forms-editor-links"><a href={`/builder/edit/${template.id}`} title={t('builder.forms.editInBuilder')}>{t('builder.forms.editInBuilder')}</a><a href={`/runtime/${template.id}?preview=1`} title={t('builder.forms.previewForm')}>{t('builder.forms.previewForm')}</a><a href={`/admin/xlsform?replace=${template.id}`} title={t('builder.forms.replaceXlsform')}>{t('builder.forms.replaceXlsform')}</a></div></div>{runtime?.pages.map((page) => <div className="forms-page" key={page.id}><h3>{page.title}</h3>{page.sections.map((section) => <div key={section.id}><h4>{section.title}</h4><ol>{section.rows.flatMap((row) => row.columns.flatMap((column) => column.components)).map((component) => <li key={component.id}>{component.label}<small>{component.type}</small></li>)}</ol></div>)}</div>)}{!questions.length && <p>{t('builder.forms.noQuestionsYet')}</p>}<CollectionPanel template={template} onIssued={() => void fetchPublicLinks(templateId).then(setLinks).catch(() => undefined)} /></section>}
    {tab === 'datos' && <section className="forms-detail-panel forms-data-panel"><div className="forms-data-toolbar"><div><h2>{t('builder.forms.formResponses')}</h2><p>{t('builder.forms.responseSummary', { count: template.submissions_count ?? 0 })}</p></div><a className="forms-primary-link" href={`/reports/form/${template.id}`}>{t('builder.forms.viewReport')}</a></div><RecordTable templateId={template.id} embedded /></section>}
    {tab === 'configuracion' && <section className="forms-detail-panel"><h2>{t('builder.forms.formProperties')}</h2><div className="forms-properties"><label>{t('builder.forms.formNameLabel')}<input value={formName} maxLength={180} onChange={(event) => setFormName(event.target.value)} /></label><label>{t('builder.forms.descriptionLabel')}<textarea rows={3} value={formDescription} onChange={(event) => setFormDescription(event.target.value)} /></label><button type="button" disabled={busy || !formName.trim()} onClick={() => void saveProperties()}>{t('builder.forms.saveNameDescription')}</button></div><h2>{t('builder.forms.publishAndResponses')}</h2><p>{t('builder.forms.publishDescription')}</p><div className="forms-actions">{template.status === 'draft' && <button type="button" disabled={busy} onClick={() => void changeStatus('published')}>{t('builder.forms.publishForm')}</button>}{template.status === 'published' && <button type="button" disabled={busy} onClick={() => void changeStatus('paused')}>{t('builder.forms.pauseResponses')}</button>}{template.status === 'paused' && <button type="button" disabled={busy} onClick={() => void changeStatus('published')}>{t('builder.forms.resumeResponses')}</button>}{template.status !== 'archived' && <button type="button" className="forms-archive-button" disabled={busy} onClick={() => void changeStatus('archived')}>{t('builder.forms.archiveForm')}</button>}{template.status === 'archived' && <button type="button" disabled={busy} onClick={() => void changeStatus('draft')}>{t('builder.forms.restoreAsDraft')}</button>}</div><div className="forms-schedule"><h3>{t('builder.forms.receptionWindow')}</h3><p>{t('builder.forms.receptionWindowHint')}</p><div className="forms-schedule-fields"><label>{t('builder.forms.startDateTime')}<input type="datetime-local" value={startsAt} onChange={(event) => setStartsAt(event.target.value)} /></label><label>{t('builder.forms.endDateTime')}<input type="datetime-local" value={endsAt} onChange={(event) => setEndsAt(event.target.value)} /></label></div><button type="button" disabled={busy || template.status === 'archived'} onClick={() => void saveSchedule()}>{t('builder.forms.saveDates')}</button></div><div className="forms-public-links"><h3>{t('builder.forms.publicLinks')}</h3><p>{t('builder.forms.linksDescription', { count: links.length })}</p><button type="button" disabled={busy || template.status !== 'published' || template.availability === 'closed'} onClick={() => void makeLink()}>{t('builder.forms.generatePublicLink')}</button>{newPublicUrl && <label>{t('builder.forms.newLinkCopy')}<input readOnly value={newPublicUrl} onFocus={(event) => event.target.select()} /></label>}<a href={`/admin/public-links?template=${template.id}`}>{t('builder.forms.manageLinks')}</a></div></section>}
    {tab === 'configuracion' && <section className="forms-detail-panel"><ParticipantSourcePanel template={template} onUpdate={setTemplate} /></section>}
    {tab === 'configuracion' && <section className="forms-detail-panel"><FormLookupPanel templateId={template.id} /></section>}
    {tab === 'configuracion' && canDelete && <section className="forms-detail-panel"><h2>{t('builder.forms.deleteForm')}</h2><p>{t('builder.forms.deleteFormDescription')}</p>{!showDelete ? <button type="button" disabled={busy} onClick={() => setShowDelete(true)}>{t('builder.forms.deleteForm')}</button> : <div className="forms-properties"><label>{t('builder.forms.typeNameToConfirm')}<strong>{template.name}</strong><input value={deleteConfirmation} onChange={(event) => setDeleteConfirmation(event.target.value)} /></label><div className="forms-actions"><button type="button" disabled={busy || deleteConfirmation !== template.name} onClick={() => void removeForm()}>{t('builder.forms.confirmDelete')}</button><button type="button" disabled={busy} onClick={() => { setShowDelete(false); setDeleteConfirmation(''); }}>{t('app.cancel')}</button></div></div>}</section>}
    </>}
    {message && <p role="status" className="forms-feedback">{message}</p>}
  </main></AppShell>;
}
