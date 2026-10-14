import { useEffect, useState } from 'react';

import { useI18n } from '../../i18n';
import { authorizationHeader, hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchCaseAssignees } from '../participants/api';
import type { CaseAssignee } from '../participants/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type SavedExport = { id: string; name: string; template_id?: string | null; frequency: string; recipient_user_id: string; last_run_at?: string | null };
type ExportFile = { id: string; created_at: string; bytes: number };

export function SavedExportsPanel({ projectId, templates }: { projectId: string; templates: { template_id: string; template_name: string }[] }) {
  const { t } = useI18n();
  const [items, setItems] = useState<SavedExport[]>([]);
  const [users, setUsers] = useState<CaseAssignee[]>([]);
  const [files, setFiles] = useState<Record<string, ExportFile[]>>({});
  const [name, setName] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [frequency, setFrequency] = useState('manual');
  const [recipient, setRecipient] = useState('');
  const [message, setMessage] = useState('');
  const canExport = hasAnyCurrentProjectPermission(['reports.export']);

  async function request(path: string, init?: RequestInit): Promise<Response> {
    const response = await fetch(`${API_BASE_URL}/saved-exports${path}`, { ...init, headers: { ...authorizationHeader(), 'Content-Type': 'application/json' } });
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || t('reports.exports.operationError'));
    return response;
  }
  async function refresh() { setItems(await (await request(`/${projectId}`)).json()); }
  useEffect(() => { if (!canExport) return; void refresh().catch((error: Error) => setMessage(error.message)); void fetchCaseAssignees(projectId).then(setUsers).catch(() => {}); }, [projectId, canExport]);

  async function create() {
    try {
      await request(`/${projectId}`, { method: 'POST', body: JSON.stringify({ name, template_id: templateId || null, frequency, recipient_user_id: recipient }) });
      setName(''); await refresh(); setMessage(t('reports.exports.saved'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('reports.exports.saveError')); }
  }
  async function run(id: string) {
    try { await request(`/${id}/run`, { method: 'POST' }); await showFiles(id); setMessage(t('reports.exports.generated')); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('reports.exports.generateError')); }
  }
  async function showFiles(id: string) {
    try { setFiles((current) => ({ ...current, [id]: [] })); const data = await (await request(`/${id}/files`)).json(); setFiles((current) => ({ ...current, [id]: data })); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('reports.exports.filesError')); }
  }
  async function download(id: string, fileId: string, csv: boolean) {
    try {
      const blob = await (await request(`/${id}/files/${fileId}`)).blob();
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `exportacion-${fileId}.${csv ? 'csv' : 'xlsx'}`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setMessage(error instanceof Error ? error.message : t('reports.exports.downloadError')); }
  }
  if (!canExport) return null;
  return <section className="participant-summary-card"><h3>{t('reports.exports.title')}</h3><p>{t('reports.exports.description')}</p><div className="participants-group-toolbar"><input aria-label={t('reports.exports.nameAria')} placeholder={t('reports.exports.namePlaceholder')} value={name} onChange={(event) => setName(event.target.value)} /><select aria-label={t('reports.exports.formAria')} value={templateId} onChange={(event) => setTemplateId(event.target.value)}><option value="">{t('reports.exports.projectSummary')}</option>{templates.map((item) => <option key={item.template_id} value={item.template_id}>{item.template_name}</option>)}</select><select aria-label={t('reports.exports.frequencyAria')} value={frequency} onChange={(event) => setFrequency(event.target.value)}><option value="manual">{t('reports.exports.frequencyManual')}</option><option value="daily">{t('reports.exports.frequencyDaily')}</option><option value="weekly">{t('reports.exports.frequencyWeekly')}</option></select><select aria-label={t('reports.exports.recipientAria')} value={recipient} onChange={(event) => setRecipient(event.target.value)}><option value="">{t('reports.exports.selectRecipient')}</option>{users.map((user) => <option key={user.id} value={user.id}>{user.full_name}</option>)}</select><button type="button" disabled={name.trim().length < 3 || !recipient} onClick={() => void create()}>{t('reports.exports.save')}</button></div>{message && <p role="status">{message}</p>}{items.map((item) => <article key={item.id} className="participant-summary-card"><strong>{item.name}</strong> · {item.frequency} · {item.last_run_at ? t('reports.exports.lastRun', { date: new Date(item.last_run_at).toLocaleString() }) : t('reports.exports.noRuns')} <button type="button" onClick={() => void run(item.id)}>{t('reports.exports.generateNow')}</button> <button type="button" onClick={() => void showFiles(item.id)}>{t('reports.exports.files')}</button> <button type="button" onClick={() => { if (!window.confirm(t('reports.exports.confirmDelete', { name: item.name }))) return; void request(`/${item.id}`, { method: 'DELETE' }).then(refresh).catch((error: Error) => setMessage(error.message)); }}>{t('reports.exports.delete')}</button>{files[item.id]?.map((file) => <p key={file.id}>{new Date(file.created_at).toLocaleString()} · {Math.round(file.bytes / 1024)} KB <button type="button" onClick={() => void download(item.id, file.id, Boolean(item.template_id))}>{t('reports.exports.download')}</button></p>)}</article>)}</section>;
}
