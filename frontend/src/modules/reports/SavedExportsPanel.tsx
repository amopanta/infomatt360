import { useEffect, useState } from 'react';

import { authorizationHeader, hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchCaseAssignees } from '../participants/api';
import type { CaseAssignee } from '../participants/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type SavedExport = { id: string; name: string; template_id?: string | null; frequency: string; recipient_user_id: string; last_run_at?: string | null };
type ExportFile = { id: string; created_at: string; bytes: number };

export function SavedExportsPanel({ projectId, templates }: { projectId: string; templates: { template_id: string; template_name: string }[] }) {
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
    if (!response.ok) throw new Error((await response.json().catch(() => null))?.detail || 'No fue posible completar la operación.');
    return response;
  }
  async function refresh() { setItems(await (await request(`/${projectId}`)).json()); }
  useEffect(() => { if (!canExport) return; void refresh().catch((error: Error) => setMessage(error.message)); void fetchCaseAssignees(projectId).then(setUsers).catch(() => {}); }, [projectId, canExport]);

  async function create() {
    try {
      await request(`/${projectId}`, { method: 'POST', body: JSON.stringify({ name, template_id: templateId || null, frequency, recipient_user_id: recipient }) });
      setName(''); await refresh(); setMessage('Exportación guardada.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible guardar la exportación.'); }
  }
  async function run(id: string) {
    try { await request(`/${id}/run`, { method: 'POST' }); await showFiles(id); setMessage('Archivo generado.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible generar el archivo.'); }
  }
  async function showFiles(id: string) {
    try { setFiles((current) => ({ ...current, [id]: [] })); const data = await (await request(`/${id}/files`)).json(); setFiles((current) => ({ ...current, [id]: data })); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible consultar los archivos.'); }
  }
  async function download(id: string, fileId: string, csv: boolean) {
    try {
      const blob = await (await request(`/${id}/files/${fileId}`)).blob();
      const url = URL.createObjectURL(blob); const anchor = document.createElement('a');
      anchor.href = url; anchor.download = `exportacion-${fileId}.${csv ? 'csv' : 'xlsx'}`; anchor.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible descargar el archivo.'); }
  }
  if (!canExport) return null;
  return <section className="participant-summary-card"><h3>Exportaciones guardadas y programadas</h3><p>Guarda una exportación del proyecto o de un formulario. Las programadas generan un archivo diario o semanal y avisan al destinatario.</p><div className="participants-group-toolbar"><input aria-label="Nombre de exportación" placeholder="Nombre de la exportación" value={name} onChange={(event) => setName(event.target.value)} /><select aria-label="Formulario" value={templateId} onChange={(event) => setTemplateId(event.target.value)}><option value="">Resumen del proyecto</option>{templates.map((item) => <option key={item.template_id} value={item.template_id}>{item.template_name}</option>)}</select><select aria-label="Frecuencia" value={frequency} onChange={(event) => setFrequency(event.target.value)}><option value="manual">Manual</option><option value="daily">Diaria</option><option value="weekly">Semanal</option></select><select aria-label="Destinatario" value={recipient} onChange={(event) => setRecipient(event.target.value)}><option value="">Seleccionar destinatario</option>{users.map((user) => <option key={user.id} value={user.id}>{user.full_name}</option>)}</select><button type="button" disabled={name.trim().length < 3 || !recipient} onClick={() => void create()}>Guardar</button></div>{message && <p role="status">{message}</p>}{items.map((item) => <article key={item.id} className="participant-summary-card"><strong>{item.name}</strong> · {item.frequency} · {item.last_run_at ? `Última ejecución: ${new Date(item.last_run_at).toLocaleString()}` : 'Sin ejecuciones'} <button type="button" onClick={() => void run(item.id)}>Generar ahora</button> <button type="button" onClick={() => void showFiles(item.id)}>Archivos</button> <button type="button" onClick={() => { if (!window.confirm(`¿Eliminar ${item.name} y sus archivos?`)) return; void request(`/${item.id}`, { method: 'DELETE' }).then(refresh).catch((error: Error) => setMessage(error.message)); }}>Eliminar</button>{files[item.id]?.map((file) => <p key={file.id}>{new Date(file.created_at).toLocaleString()} · {Math.round(file.bytes / 1024)} KB <button type="button" onClick={() => void download(item.id, file.id, Boolean(item.template_id))}>Descargar</button></p>)}</article>)}</section>;
}
