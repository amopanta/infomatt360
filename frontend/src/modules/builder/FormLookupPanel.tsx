import { useEffect, useState } from 'react';
import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type Lookup = { name: string; row_count: number; columns: string[]; checksum: string };

export function FormLookupPanel({ templateId }: { templateId: string }) {
  const [lookups, setLookups] = useState<Lookup[]>([]);
  const [selected, setSelected] = useState<File | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  async function refresh() {
    const response = await fetch(`${API_BASE_URL}/form-lookups/templates/${templateId}`, { headers: authorizationHeader() });
    if (!response.ok) throw new Error('No fue posible consultar los CSV del formulario.');
    setLookups(await response.json());
  }
  useEffect(() => { void refresh().catch((error: Error) => setMessage(error.message)); }, [templateId]);

  async function upload() {
    if (!selected) return;
    setBusy(true); setMessage('');
    try {
      const form = new FormData(); form.append('upload', selected);
      const response = await fetch(`${API_BASE_URL}/form-lookups/templates/${templateId}`, { method: 'POST', headers: authorizationHeader(), body: form });
      if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail || 'No fue posible cargar el CSV.'); }
      await refresh(); window.dispatchEvent(new Event('infomatt:pull-updated')); setSelected(null); setMessage('CSV cargado. pulldata() ya puede consultarlo.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible cargar el CSV.'); }
    finally { setBusy(false); }
  }

  return <div className="forms-public-links"><h3>Grupos Pull del formulario</h3><p>Adjunta el CSV con el mismo nombre usado en la fórmula XLSForm. Ejemplo: <code>pulldata('familias', 'nombre', 'codigo', ${'{'}codigo_participante{'}'})</code> consulta familias.csv.</p>
    <label>Archivo CSV UTF-8<input type="file" accept=".csv,text/csv" onChange={(event) => setSelected(event.target.files?.[0] || null)} /></label>
    <button type="button" disabled={!selected || busy} onClick={() => void upload()}>{busy ? 'Cargando…' : 'Cargar CSV'}</button>
    {lookups.length > 0 && <ul>{lookups.map((item) => <li key={item.name}><strong>{item.name}.csv</strong> · {item.row_count} filas · {item.columns.join(', ')}</li>)}</ul>}
    {message && <p role="status">{message}</p>}
  </div>;
}

export function BulkPullPanel({ projectId, forms }: { projectId: string; forms: Array<{ id: string; name: string }> }) {
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
      if (!response.ok) { const payload = await response.json().catch(() => null); throw new Error(payload?.detail || 'No fue posible asignar el grupo Pull.'); }
      window.dispatchEvent(new Event('infomatt:pull-updated'));
      setMessage(`${file.name} asignado a ${selected.length} formulario(s).`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible asignar el grupo Pull.'); }
    finally { setBusy(false); }
  }

  return <section className="forms-detail-panel"><h2>Asignación masiva de grupo Pull</h2><p>Carga un CSV y selecciona los formularios que usarán la misma tabla. Si ya existe un CSV con ese nombre, se actualizará en esos formularios.</p>
    <label>Archivo CSV UTF-8<input type="file" accept=".csv,text/csv" onChange={(event) => setFile(event.target.files?.[0] || null)} /></label>
    <fieldset><legend>Formularios de destino</legend>{forms.map((form) => <label key={form.id} className="forms-pull-choice"><input type="checkbox" checked={selected.includes(form.id)} onChange={(event) => setSelected((current) => event.target.checked ? [...current, form.id] : current.filter((id) => id !== form.id))} /> {form.name}</label>)}</fieldset>
    <button type="button" disabled={!file || !selected.length || busy} onClick={() => void assign()}>{busy ? 'Asignando…' : 'Asignar a formularios'}</button>{message && <p role="status">{message}</p>}
  </section>;
}
