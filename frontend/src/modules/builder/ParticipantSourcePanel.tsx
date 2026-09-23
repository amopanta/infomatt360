import { useEffect, useState } from 'react';
import { authorizationHeader } from '../auth/session';
import type { TemplateSummary } from '../records/api';
import { fetchEligibleParticipants, setParticipantSource, type ParticipantSource } from './api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const DEFAULT_SOURCE: ParticipantSource = { mode: 'all', participant_ids: [], municipality: '', previous_template_id: null, required_status: 'submitted' };

export function ParticipantSourcePanel({ template, onUpdate }: { template: TemplateSummary; onUpdate: (value: TemplateSummary) => void }) {
  const [source, setSource] = useState<ParticipantSource>(template.participant_source || DEFAULT_SOURCE);
  const [forms, setForms] = useState<TemplateSummary[]>([]);
  const [people, setPeople] = useState<Array<{ id: string; full_name: string; external_code?: string | null }>>([]);
  const [eligible, setEligible] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void Promise.all([
      fetch(`${API_BASE_URL}/builder/templates/${template.project_id}`, { headers: authorizationHeader() }).then((response) => response.json()),
      fetch(`${API_BASE_URL}/participants/project/${template.project_id}`, { headers: authorizationHeader() }).then((response) => response.json()),
    ]).then(([templates, participants]) => { setForms(templates); setPeople(participants); }).catch(() => setMessage('No fue posible cargar formularios o participantes.'));
  }, [template.project_id]);

  async function save() {
    setBusy(true); setMessage('');
    try {
      const updated = await setParticipantSource(template.id, source);
      onUpdate(updated);
      setEligible((await fetchEligibleParticipants(template.id)).length);
      setMessage('Fuente guardada. Se aplicará a las nuevas respuestas.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible guardar.'); }
    finally { setBusy(false); }
  }

  return <div className="forms-public-links"><h3>Fuente de participantes</h3><p>Define quién puede responder. La regla se verifica al guardar cada respuesta.</p>
    <label>Origen<select value={source.mode} onChange={(event) => setSource({ ...source, mode: event.target.value as ParticipantSource['mode'] })}>
      <option value="all">Todos los participantes</option><option value="list">Lista seleccionada</option><option value="filter">Municipio</option><option value="form">Formulario anterior completado</option>
    </select></label>
    {source.mode === 'list' && <label>Participantes<select multiple size={Math.min(8, Math.max(3, people.length))} value={source.participant_ids} onChange={(event) => setSource({ ...source, participant_ids: Array.from(event.target.selectedOptions, (option) => option.value) })}>{people.map((person) => <option key={person.id} value={person.id}>{person.full_name} {person.external_code || ''}</option>)}</select></label>}
    {source.mode === 'filter' && <label>Municipio<input value={source.municipality || ''} onChange={(event) => setSource({ ...source, municipality: event.target.value })} /></label>}
    {source.mode === 'form' && <><label>Formulario anterior<select value={source.previous_template_id || ''} onChange={(event) => setSource({ ...source, previous_template_id: event.target.value || null })}><option value="">Selecciona un formulario</option>{forms.filter((form) => form.id !== template.id).map((form) => <option key={form.id} value={form.id}>{form.name}</option>)}</select></label><label>Estado requerido<select value={source.required_status} onChange={(event) => setSource({ ...source, required_status: event.target.value })}><option value="submitted">Enviado</option><option value="completed">Completado</option><option value="approved">Aprobado</option></select></label></>}
    <button type="button" disabled={busy} onClick={() => void save()}>Guardar fuente</button>{eligible !== null && <p>{eligible} participante(s) elegibles actualmente.</p>}{message && <p role="status">{message}</p>}
  </div>;
}
