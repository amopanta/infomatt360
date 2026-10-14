import { useEffect, useState } from 'react';
import { authorizationHeader } from '../auth/session';
import { useI18n } from '../../i18n';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type Lookup = { name: string; row_count: number; columns: string[]; checksum: string };

export function FormLookupPanel({ templateId }: { templateId: string }) {
  const { t } = useI18n();
  const [lookups, setLookups] = useState<Lookup[]>([]);
  const [selected, setSelected] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const response = await fetch(`${API_BASE_URL}/form-lookups/templates/${templateId}`, { headers: authorizationHeader() });
    if (!response.ok) throw new Error(t('builder.lookup.csvLoadFailed'));
    setLookups(await response.json());
  }
  useEffect(() => { void refresh().catch((error: Error) => setMessage(error.message)); }, [templateId]);

  async function upload() {
    if (!selected) return;
    setBusy(true); setMessage('');
    try {
      const form = new FormData(); form.append('upload', selected);
      const response = await fetch(`${API_BASE_URL}/form-lookups/templates/${templateId}`, { method: 'POST', headers: authorizationHeader(), body: form });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail || t('builder.lookup.csvUploadFailed')); }
      await refresh(); window.dispatchEvent(new Event('infomatt:pull-updated')); setSelected(null); setMessage(t('builder.lookup.csvUploaded'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('builder.lookup.csvUploadFailed')); }
    finally { setBusy(false); }
  }

  return <div className="forms-public-links"><h3>{t('builder.lookup.title')}</h3><p>{t('builder.lookup.description')} <code>pulldata('familias', 'nombre', 'codigo', ${'{'}codigo_participante{'}'})</code> consulta familias.csv.</p>
    <label>{t('builder.lookup.csvFileLabel')}<input type="file" accept=".csv,text/csv" onChange={(event) => setSelected(event.target.files?.[0] || null)} /></label>
    <button type="button" disabled={!selected || busy} onClick={() => void upload()}>{busy ? t('builder.lookup.uploading') : t('builder.lookup.uploadCsv')}</button>
    {lookups.length > 0 && <ul>{lookups.map((item) => <li key={item.name}><strong>{item.name}.csv</strong> · {item.row_count} filas · {item.columns.join(', ')}</li>)}</ul>}
    {message && <p role="status">{message}</p>}
  </div>;
}

export function BulkPullPanel({ projectId, forms }: { projectId: string; forms: Array<{ id: string; name: string }> }) {
  const { t } = useI18n();
  const [file, setFile] = useState<File | null>(null);
  const [selected, setSelected] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  async function assign() {
    if (!file || !selected.length) return;
    setBusy(true); setMessage('');
    try {
      const body = new FormData();
      body.append('upload', file);
      body.append('template_ids', JSON.stringify(selected));
      const response = await fetch(`${API_BASE_URL}/form-lookups/projects/${projectId}/assign`, { method: 'POST', headers: authorizationHeader(), body });
      if (!response.ok) { const payload = await response.json().catch(() => null); throw new Error(payload?.detail || t('builder.lookup.assignFailed')); }
      window.dispatchEvent(new Event('infomatt:pull-updated'));
      setMessage(t('builder.lookup.assignSuccess', { name: file.name, count: selected.length }));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('builder.lookup.assignFailed')); }
    finally { setBusy(false); }
  }

  return <section className="forms-detail-panel forms-pull-panel"><h2>{t('builder.lookup.bulkTitle')}</h2><p>{t('builder.lookup.bulkDescription')}</p>
    <label className="forms-pull-upload">{t('builder.lookup.bulkFileLabel')}<input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
    <fieldset><legend>{t('builder.lookup.destinationForms', { count: selected.length })}</legend><div className="forms-pull-options">{forms.map((form) => <label key={form.id} className="forms-pull-choice"><input type="checkbox" checked={selected.includes(form.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, form.id] : current.filter((id) => id !== form.id))} /> {form.name}</label>)}</div></fieldset>
    <button type="button" disabled={!file || !selected.length || busy} onClick={() => void assign()}>{busy ? t('builder.lookup.assigning') : t('builder.lookup.assignToForms')}</button>{message && <p role="status">{message}</p>}
  </section>;
}
