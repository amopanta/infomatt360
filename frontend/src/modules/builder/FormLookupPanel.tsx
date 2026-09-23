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
      await refresh(); setSelected(null); setMessage('CSV cargado. pulldata() ya puede consultarlo.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible cargar el CSV.'); }
    finally { setBusy(false); }
  }

  return <div className="forms-public-links"><h3>Archivos CSV para pulldata()</h3><p>Adjunta el CSV con el mismo nombre usado en la fórmula XLSForm. Ejemplo: <code>pulldata('familias', 'nombre', 'codigo', ${'{'}codigo_participante{'}'})</code> consulta familias.csv.</p>
    <label>Archivo CSV UTF-8<input type="file" accept=".csv,text/csv" onChange={(event) => setSelected(event.target.files?.[0] || null)} /></label>
    <button type="button" disabled={!selected || busy} onClick={() => void upload()}>{busy ? 'Cargando…' : 'Cargar CSV'}</button>
    {lookups.length > 0 && <ul>{lookups.map((item) => <li key={item.name}><strong>{item.name}.csv</strong> · {item.row_count} filas · {item.columns.join(', ')}</li>)}</ul>}
    {message && <p role="status">{message}</p>}
  </div>;
}
