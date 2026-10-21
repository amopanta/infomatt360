/** Importar desde la base externa (docs/146): participantes, respuestas de un formulario o asignaciones. */
import { useEffect, useState } from 'react';
import { jsonAuthHeaders } from '../auth/session';
import { createScheduledTask } from './schedulerApi';
import type { MirrorTarget } from './mirrorApi';

const API = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
type Entity = 'participants' | 'records' | 'assignments';
type DbImport = { id: string; name: string; entity: Entity; source_table: string; template_id: string | null; mapping: Record<string, string>; key_column: string; cursor_column: string | null; status: string; last_result: string | null };
type Described = { tables: string[]; columns: string[]; suggested_mapping: Record<string, string>; target_fields: string[] };
type RunResult = { rows_read: number; created: number; updated: number; unchanged: number; failed: number; errors: { row: number; key: string; error: string }[]; preview?: { row: number; key: string; outcome: string; message?: string }[] };

const ENTITY_LABELS: Record<Entity, string> = { participants: 'Participantes', records: 'Respuestas de un formulario', assignments: 'Asignaciones de un formulario' };
const FIELD_LABELS: Record<string, string> = {
  document_id: 'Documento', external_code: 'Código', full_name: 'Nombre completo', participant_type: 'Tipo', department: 'Departamento',
  municipality: 'Municipio', group_name: 'Grupo', participant_key: 'Participante (documento o código)', responsible_email: 'Correo del responsable',
};
const OUTCOMES: Record<string, string> = { created: 'Se crea', updated: 'Se actualiza', unchanged: 'Sin cambios', failed: 'Error' };

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API}/db-sync${path}`, { ...init, headers: jsonAuthHeaders() });
  if (!response.ok) {
    const detail = (await response.json().catch(() => null))?.detail;
    throw new Error(typeof detail === 'string' ? detail : 'No fue posible completar la operación.');
  }
  return response.json() as Promise<T>;
}

async function fetchForms(projectId: string): Promise<{ id: string; name: string }[]> {
  const response = await fetch(`${API}/planner/${projectId}/catalog`, { headers: jsonAuthHeaders() });
  return response.ok ? (await response.json()).activities : [];
}

export function DbImportPanel({ projectId, source }: { projectId: string; source: MirrorTarget }) {
  const [imports, setImports] = useState<DbImport[]>([]);
  const [forms, setForms] = useState<{ id: string; name: string }[]>([]);
  const [entity, setEntity] = useState<Entity>('participants');
  const [templateId, setTemplateId] = useState('');
  const [table, setTable] = useState('');
  const [described, setDescribed] = useState<Described | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [keyColumn, setKeyColumn] = useState('');
  const [cursorColumn, setCursorColumn] = useState('');
  const [name, setName] = useState('');
  const [result, setResult] = useState<RunResult | null>(null);
  const [message, setMessage] = useState('');

  const load = () => call<DbImport[]>(`/${projectId}/imports`).then((rows) => setImports(rows.filter((row) => row.status !== 'deleted'))).catch(() => setImports([]));
  useEffect(() => { void load(); void fetchForms(projectId).then(setForms); }, [projectId, source.id]);

  async function describe(nextTable = table) {
    try {
      const params = new URLSearchParams({ entity, ...(nextTable ? { source_table: nextTable } : {}), ...(templateId ? { template_id: templateId } : {}) });
      const next = await call<Described>(`/${projectId}/sources/${source.id}/describe?${params}`);
      setDescribed(next);
      if (nextTable) { setMapping(next.suggested_mapping); setKeyColumn(next.suggested_mapping.document_id || next.suggested_mapping.participant_key || next.columns[0] || ''); }
      setMessage('');
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  async function create() {
    try {
      const clean = Object.fromEntries(Object.entries(mapping).filter(([, column]) => column));
      await call(`/${projectId}/imports`, { method: 'POST', body: JSON.stringify({ source_id: source.id, name, entity, source_table: table,
        template_id: entity === 'participants' ? null : templateId, mapping: clean, key_column: keyColumn, cursor_column: cursorColumn || null }) });
      setMessage('Importación creada. Usa «Vista previa» antes de ejecutarla.');
      setName(''); setDescribed(null); setTable(''); await load();
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  async function act(job: DbImport, action: 'preview' | 'run') {
    try { setResult(await call<RunResult>(`/imports/${job.id}/${action}`, { method: 'POST' })); await load(); setMessage(action === 'preview' ? 'Vista previa: no se escribió nada.' : 'Importación ejecutada.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  async function schedule(job: DbImport) {
    const time = window.prompt('Hora diaria (HH:MM, hora de Colombia)', '03:00');
    if (!time) return;
    try {
      await createScheduledTask({ project_id: projectId, name: `Importar: ${job.name}`, task_type: 'db_import', target_id: job.id, frequency: 'daily',
        config_json: JSON.stringify({ run_time: time, timezone: 'America/Bogota' }) });
      setMessage(`Programada todos los días a las ${time}.`);
    } catch (error) { setMessage(error instanceof Error ? error.message : String(error)); }
  }

  const needsForm = entity !== 'participants';
  return <section className="db-import-panel" style={{ marginBottom: 24 }}>
    <h3>Importar desde «{source.name}» hacia InfoMatt360</h3>
    <p>Lee una tabla o vista de esta base y crea o actualiza información. Repetir la importación no duplica: cada fila se reconoce por su columna clave y solo se escribe si cambió. Un registro aprobado no se modifica.</p>
    <div className="planner-grid">
      <label>Qué importar<select value={entity} onChange={(e) => { setEntity(e.target.value as Entity); setDescribed(null); setTable(''); }}>
        {(Object.keys(ENTITY_LABELS) as Entity[]).map((key) => <option key={key} value={key}>{ENTITY_LABELS[key]}</option>)}</select></label>
      {needsForm ? <label>Formulario<select value={templateId} onChange={(e) => { setTemplateId(e.target.value); setDescribed(null); setTable(''); }}>
        <option value="">—</option>{forms.map((form) => <option key={form.id} value={form.id}>{form.name}</option>)}</select></label> : null}
      <button type="button" disabled={needsForm && !templateId} onClick={() => void describe('')}>Ver tablas de la base</button>
      {described?.tables.length ? <label>Tabla o vista<select value={table} onChange={(e) => { setTable(e.target.value); void describe(e.target.value); }}>
        <option value="">—</option>{described.tables.map((item) => <option key={item} value={item}>{item}</option>)}</select></label> : null}
    </div>
    {described && table ? <div className="db-import-mapping">
      <h4>Columnas (sugeridas por nombre; revísalas)</h4>
      <div className="planner-grid">
        {described.target_fields.map((field) => <label key={field}>{FIELD_LABELS[field] ?? field}<select value={mapping[field] ?? ''} onChange={(e) => setMapping({ ...mapping, [field]: e.target.value })}>
          <option value="">(no importar)</option>{described.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label>)}
        <label>Columna clave (identifica cada fila)<select value={keyColumn} onChange={(e) => setKeyColumn(e.target.value)}>{described.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label>
        <label>Columna de avance (opcional: fecha o id creciente, para traer solo lo nuevo)<select value={cursorColumn} onChange={(e) => setCursorColumn(e.target.value)}>
          <option value="">(leer todo cada vez)</option>{described.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label>
        <label className="planner-wide">Nombre de la importación<input value={name} onChange={(e) => setName(e.target.value)} placeholder="Ej. Padrón de beneficiarios" /></label>
      </div>
      <button type="button" disabled={name.trim().length < 3 || !keyColumn} onClick={() => void create()}>Crear importación</button>
    </div> : null}
    {message ? <p role="status">{message}</p> : null}
    {imports.length ? <table className="data-table"><thead><tr><th>Importación</th><th>Qué</th><th>Tabla</th><th>Último resultado</th><th /></tr></thead>
      <tbody>{imports.map((job) => <tr key={job.id}><td>{job.name}</td><td>{ENTITY_LABELS[job.entity]}</td><td>{job.source_table}</td><td style={{ fontSize: '0.85em' }}>{job.last_result ?? '—'}</td>
        <td><button className="btn btn-sm" onClick={() => void act(job, 'preview')}>Vista previa</button> <button className="btn btn-sm" onClick={() => void act(job, 'run')}>Ejecutar ahora</button> <button className="btn btn-sm" onClick={() => void schedule(job)}>Programar diario</button></td></tr>)}</tbody></table> : null}
    {result ? <div className="db-import-result">
      <p>Leídas {result.rows_read} · creadas {result.created} · actualizadas {result.updated} · sin cambios {result.unchanged} · con error {result.failed}</p>
      {result.preview?.length ? <table className="data-table"><thead><tr><th>Fila</th><th>Clave</th><th>Resultado</th><th>Detalle</th></tr></thead>
        <tbody>{result.preview.map((row) => <tr key={row.row}><td>{row.row}</td><td>{row.key}</td><td>{OUTCOMES[row.outcome] ?? row.outcome}</td><td>{row.message ?? ''}</td></tr>)}</tbody></table> : null}
      {!result.preview && result.errors.length ? <table className="data-table"><thead><tr><th>Fila</th><th>Clave</th><th>Error</th></tr></thead>
        <tbody>{result.errors.map((row) => <tr key={`${row.row}-${row.key}`}><td>{row.row}</td><td>{row.key}</td><td>{row.error}</td></tr>)}</tbody></table> : null}
    </div> : null}
  </section>;
}
