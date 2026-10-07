import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchParticipantHistory, type ParticipantHistoryItem } from '../participants/api';
import { fetchRecord, type RuntimeRecord } from '../records/api';
import { fetchMyFormAssignments, type MyFormAssignment } from './myFormsApi';

const labels: Record<string, string> = { assigned: 'Asignado', in_progress: 'En curso', completed: 'Completado', closed: 'Cerrado' };
const canCapture = (row: MyFormAssignment) => ['assigned', 'in_progress'].includes(row.assignment_status);

function displayValue(raw: string): string {
  try { const value: unknown = JSON.parse(raw); return typeof value === 'string' ? value : JSON.stringify(value); }
  catch { return raw; }
}

export function MyFormsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [assignments, setAssignments] = useState<MyFormAssignment[]>([]);
  const [message, setMessage] = useState('Cargando tus formularios...');
  const [query, setQuery] = useState('');
  const [participantId, setParticipantId] = useState('');
  const [templateId, setTemplateId] = useState('');
  const [history, setHistory] = useState<ParticipantHistoryItem[]>([]);
  const [record, setRecord] = useState<RuntimeRecord | null>(null);

  async function refresh() {
    if (!projectId) { setMessage('Selecciona un proyecto para ver tus formularios.'); return; }
    try { setAssignments(await fetchMyFormAssignments(projectId)); setMessage(''); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible cargar tus formularios.'); }
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
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible abrir la respuesta.'); }
  }

  return <AppShell title="Mis formularios"><main className="forms-home my-forms-journey">
    <header className="forms-home-head"><div><h1>Mis formularios asignados</h1><p>Consulta primero el participante y luego sus actividades.</p></div><button type="button" onClick={() => void refresh()}>Actualizar asignaciones</button></header>
    {message && <p role="status">{message}</p>}
    {!message && !assignments.length && <p>No hay formularios publicados con participantes asignados en este proyecto. Revisa el selector <strong>Proyecto</strong> de arriba.</p>}
    {closed.length > 0 && <section className="forms-detail-panel">
      {record ? <><button type="button" onClick={() => setRecord(null)}>← Volver a respuestas</button><p className="my-forms-eyebrow">Respuesta enviada</p><h2>{currentForm?.template_name} — {selected?.participant_name}</h2><div className="my-forms-values">{record.values.map((value) => <div key={value.id}><strong>{value.field_name}</strong><span>{displayValue(value.field_value_json)}</span></div>)}</div><a href={`/records/${record.template_id}?recordId=${record.id}`}>Abrir registro completo</a></> :
      templateId ? <><button type="button" onClick={() => setTemplateId('')}>← Volver a formularios</button><p className="my-forms-eyebrow">Respuestas enviadas</p><h2>{currentForm?.template_name} — {selected?.participant_name}</h2>{responses.length ? responses.map((item) => <div className="my-forms-row" key={item.record_id}><span>{new Date(item.created_at).toLocaleString()} · {item.status}</span><button type="button" onClick={() => void openRecord(item.record_id)}>Ver respuesta</button></div>) : <p>Este formulario todavía no tiene respuestas.</p>}{currentForm && canCapture(currentForm) && <a href={`/runtime/${templateId}?participantId=${participantId}`}>Diligenciar formulario</a>}</> :
      selected ? <><button type="button" onClick={() => setParticipantId('')}>← Volver a participantes</button><div className="my-forms-heading"><div><p className="my-forms-eyebrow">Participante seleccionado</p><h2>{selected.participant_name}</h2><p>{selected.document_id ? `Documento ${selected.document_id}` : ''}{selected.external_code ? ` · ${selected.external_code}` : ''}</p></div><span>{applied} de {forms.length} aplicados</span></div>{forms.map((row) => { const hasResponse = history.some((item) => item.template_id === row.template_id) || Boolean(row.record_id); return <div className="my-forms-row" key={row.template_id}><div><strong>{row.template_name}</strong><small>{hasResponse ? '✓ Aplicado' : labels[row.assignment_status] || row.assignment_status}</small></div><div>{hasResponse && <button type="button" onClick={() => setTemplateId(row.template_id)}>Ver respuestas</button>}{!hasResponse && canCapture(row) && <a href={`/runtime/${row.template_id}?participantId=${participantId}`}>Diligenciar</a>}</div></div>; })}</> :
      <><h2>Participantes</h2><p>Selecciona una persona para consultar sus formularios asociados.</p><input type="search" aria-label="Buscar participante" placeholder="Buscar por nombre, cédula o código" value={query} onChange={(event) => setQuery(event.target.value)} />{visible.map((row) => <button className="my-forms-row my-forms-participant" type="button" key={row.participant_id} onClick={() => setParticipantId(row.participant_id)}><span><strong>{row.participant_name}</strong><small>{row.document_id || 'Sin documento'}{row.external_code ? ` · ${row.external_code}` : ''}</small></span><span>›</span></button>)}{!visible.length && <p>No se encontraron participantes.</p>}</>}
    </section>}
    {open.length > 0 && <section className="forms-detail-panel"><h2>Formularios abiertos</h2><p>Estos formularios conservan su forma de trabajo actual.</p>{Array.from(new Set(open.map((row) => row.template_id))).map((id) => { const rows = open.filter((row) => row.template_id === id); return <div key={id}><h3>{rows[0].template_name}</h3><div className="records-table-wrap"><table className="records-table"><thead><tr><th>Participante</th><th>Documento</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{rows.map((row) => <tr key={row.participant_id}><td>{row.participant_name}</td><td>{row.document_id || '—'}</td><td>{labels[row.assignment_status] || row.assignment_status}</td><td>{row.record_id ? <a href={`/records/${id}?recordId=${row.record_id}`}>Ver respuesta</a> : canCapture(row) ? <a href={`/runtime/${id}?participantId=${row.participant_id}`}>Diligenciar</a> : '—'}</td></tr>)}</tbody></table></div></div>; })}</section>}
  </main></AppShell>;
}
