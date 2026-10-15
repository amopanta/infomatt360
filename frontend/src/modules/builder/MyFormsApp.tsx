import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchParticipantHistory, type ParticipantHistoryItem } from '../participants/api';
import { fetchRecord, type RuntimeRecord } from '../records/api';
import { fetchMyFormAssignments, fetchOpenForms, type MyFormAssignment, type OpenForm } from './myFormsApi';
import { useI18n } from '../../i18n';

const canCapture = (row: MyFormAssignment) => ['assigned', 'in_progress'].includes(row.assignment_status);

function displayValue(raw: string): string {
  try { const value: unknown = JSON.parse(raw); return typeof value === 'string' ? value : JSON.stringify(value); }
  catch { return raw; }
}

export function MyFormsApp() {
  const { t } = useI18n();
  const labels: Record<string, string> = { assigned: t('builder.myForms.statusAssigned'), in_progress: t('builder.myForms.statusInProgress'), completed: t('builder.myForms.statusCompleted'), closed: t('builder.myForms.statusClosed') };
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [assignments, setAssignments] = useState<MyFormAssignment[]>([]);
  const [openForms, setOpenForms] = useState<OpenForm[]>([]);
  const [view, setView] = useState<'assigned' | 'open' | 'activities'>('assigned');
  const [message, setMessage] = useState(t('builder.myForms.loadingForms'));
  const [query, setQuery] = useState('');
  const [participantId, setParticipantId] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [history, setHistory] = useState<ParticipantHistoryItem[]>([]);
  const [record, setRecord] = useState<RuntimeRecord | null>(null);

  async function refresh() {
    if (!projectId) { setMessage(t('builder.myForms.selectProject')); return; }
    try {
      const [assigned, available] = await Promise.all([fetchMyFormAssignments(projectId), fetchOpenForms(projectId)]);
      setAssignments(assigned); setOpenForms(available); setMessage('');
    }
    catch (error) { setMessage(error instanceof Error ? error.message : t('builder.myForms.loadFailed')); }
  }

  useEffect(() => {
    void refresh();
    const onFocus = () => { void refresh(); };
    window.addEventListener('focus', onFocus);
    return () => window.removeEventListener('focus', onFocus);
  }, [projectId]);

  useEffect(() => {
    setHistory([]); setRecord(null); setTemplateId('');
    if (participantId) void fetchParticipantHistory(participantId).then(setHistory).catch((error: Error) => setMessage(error.message));
  }, [participantId]);

  const closed = assignments.filter((row) => row.access_mode === 'closed');
  const open = assignments.filter((row) => row.access_mode !== 'closed');
  const participants = Array.from(new Map(closed.map((row) => [row.participant_id, row])).values());
  const visible = participants.filter((row) => [row.participant_name, row.document_id, row.external_code].some((value) => String(value || '').toLowerCase().includes(query.trim().toLowerCase())));
  const selected = participants.find((row) => row.participant_id === participantId);
  const forms = closed.filter((row) => row.participant_id === participantId);
  const currentForm = forms.find((row) => row.template_id === templateId);
  const responses = history.filter((item) => item.template_id === templateId);
  const applied = forms.filter((row) => history.some((item) => item.template_id === row.template_id) || row.record_id).length;

  async function openRecord(id: string) {
    setRecord(null);
    try { setRecord(await fetchRecord(id)); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('builder.myForms.openResponseFailed')); }
  }

  return <AppShell title={t('builder.myForms.myAssignedForms')}><main className="forms-home my-forms-journey">
    <header className="forms-home-head"><div><h1>{t('builder.myForms.myAssignedForms')}</h1><p>{t('builder.myForms.consultParticipant')}</p></div><button type="button" onClick={() => void refresh()}>{t('builder.myForms.refreshAssignments')}</button></header>
    {message && <p role="status">{message}</p>}
    <nav className="my-forms-views" aria-label={t('builder.myForms.viewSelector')}>
      <button type="button" aria-current={view === 'assigned' ? 'page' : undefined} onClick={() => setView('assigned')}>{t('builder.myForms.assignedView')}</button>
      <button type="button" aria-current={view === 'open' ? 'page' : undefined} onClick={() => setView('open')}>{t('builder.myForms.openForms')}</button>
      <button type="button" aria-current={view === 'activities' ? 'page' : undefined} onClick={() => setView('activities')}>{t('builder.myForms.activitiesView')}</button>
    </nav>
    {!message && view === 'assigned' && !closed.length && <p>{t('builder.myForms.noPublishedForms')} {t('builder.myForms.checkProjectSelector')}</p>}
    {view === 'assigned' && closed.length > 0 && <section className="forms-detail-panel">
      {record ? <><button type="button" onClick={() => setRecord(null)}>{t('builder.myForms.backToResponses')}</button><p className="my-forms-eyebrow">{t('builder.myForms.responseSent')}</p><h2>{currentForm?.template_name} — {selected?.participant_name}</h2><div className="my-forms-values">{record.values.map((value) => <div key={value.id}><strong>{value.field_name}</strong><span>{displayValue(value.field_value_json)}</span></div>)}</div><a href={`/records/${record.template_id}?recordId=${record.id}`}>{t('builder.myForms.openFullRecord')}</a></> :
      templateId ? <><button type="button" onClick={() => setTemplateId('')}>{t('builder.myForms.backToForms')}</button><p className="my-forms-eyebrow">{t('builder.myForms.responsesSent')}</p><h2>{currentForm?.template_name} — {selected?.participant_name}</h2>{responses.length ? responses.map((item) => <div className="my-forms-row" key={item.record_id}><span>{new Date(item.created_at).toLocaleString()} · {item.status}</span><button type="button" onClick={() => void openRecord(item.record_id)}>{t('builder.myForms.viewResponse')}</button></div>) : <p>{t('builder.myForms.noResponsesYet')}</p>}{currentForm && canCapture(currentForm) && <a href={`/runtime/${templateId}?participantId=${participantId}`}>{t('builder.myForms.fillForm')}</a>}</> :
      selected ? <><button type="button" onClick={() => setParticipantId('')}>{t('builder.myForms.backToParticipants')}</button><div className="my-forms-heading"><div><p className="my-forms-eyebrow">{t('builder.myForms.selectedParticipant')}</p><h2>{selected.participant_name}</h2><p>{selected.document_id ? t('builder.myForms.documentLabel', { id: selected.document_id }) : ''}{selected.external_code ? ` · ${selected.external_code}` : ''}</p></div><span>{t('builder.myForms.appliedCount', { applied, total: forms.length })}</span></div>{forms.map((row) => { const hasResponse = history.some((item) => item.template_id === row.template_id) || Boolean(row.record_id); return <div className="my-forms-row" key={row.template_id}><div><strong>{row.template_name}</strong><small>{hasResponse ? t('builder.myForms.applied') : labels[row.assignment_status] || row.assignment_status}</small></div><div>{hasResponse && <button type="button" onClick={() => setTemplateId(row.template_id)}>{t('builder.myForms.viewResponses')}</button>}{!hasResponse && canCapture(row) && <a href={`/runtime/${row.template_id}?participantId=${participantId}`}>{t('builder.myForms.fillIn')}</a>}</div></div>; })}</> :
      <><h2>{t('builder.myForms.participantsTitle')}</h2><p>{t('builder.myForms.selectPersonDesc')}</p><input type="search" aria-label={t('builder.myForms.searchParticipant')} placeholder={t('builder.myForms.searchPlaceholder')} value={query} onChange={(event) => setQuery(event.target.value)} />{visible.map((row) => <button className="my-forms-row my-forms-participant" type="button" key={row.participant_id} onClick={() => setParticipantId(row.participant_id)}><span><strong>{row.participant_name}</strong><small>{row.document_id || t('builder.myForms.noDocument')}{row.external_code ? ` · ${row.external_code}` : ''}</small></span><span>›</span></button>)}{!visible.length && <p>{t('builder.myForms.noParticipantsFound')}</p>}</>}
    </section>}
    {view === 'open' && <section className="forms-detail-panel"><h2>{t('builder.myForms.openForms')}</h2><p>{t('builder.myForms.openFormsDesc')}</p>{openForms.length ? openForms.map((form) => <div className="my-forms-row" key={form.id}><strong>{form.name}</strong><a href={`/runtime/${form.id}`}>{t('builder.myForms.fillIn')}</a></div>) : <p>{t('builder.myForms.noOpenForms')}</p>}{open.length > 0 && <p>{t('builder.myForms.openAssignedCount', { count: open.length })}</p>}</section>}
    {view === 'activities' && <section className="forms-detail-panel my-forms-activity-panel"><h2>{t('builder.myForms.activitiesView')}</h2><p>{t('builder.myForms.activitiesDesc')}</p><input type="search" aria-label={t('builder.myForms.searchParticipant')} placeholder={t('builder.myForms.searchPlaceholder')} value={query} onChange={(event) => setQuery(event.target.value)} /><div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('builder.myForms.columnParticipant')}</th><th>{t('builder.myForms.columnDocument')}</th><th>{t('builder.myForms.columnCode')}</th><th>{t('builder.myForms.columnGroup')}</th><th>{t('builder.myForms.columnMunicipality')}</th><th>{t('builder.myForms.columnActivity')}</th><th>{t('builder.myForms.columnStatus')}</th><th>{t('builder.myForms.columnAction')}</th></tr></thead><tbody>{closed.filter((row) => [row.participant_name, row.document_id, row.external_code, row.template_name].some((value) => String(value || '').toLowerCase().includes(query.trim().toLowerCase()))).map((row) => <tr key={`${row.participant_id}:${row.template_id}`}><td>{row.participant_name}</td><td>{row.document_id || '—'}</td><td>{row.external_code || '—'}</td><td>{row.group_name || '—'}</td><td>{row.municipality || '—'}</td><td>{row.template_name}</td><td>{row.record_id ? t('builder.myForms.applied') : labels[row.assignment_status] || row.assignment_status}</td><td>{row.record_id ? <a href={`/records/${row.template_id}?recordId=${row.record_id}`}>{t('builder.myForms.viewResponseAction')}</a> : canCapture(row) ? <a href={`/runtime/${row.template_id}?participantId=${row.participant_id}`}>{t('builder.myForms.fillIn')}</a> : '—'}</td></tr>)}</tbody></table></div></section>}
  </main></AppShell>;
}
