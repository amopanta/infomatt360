import { useEffect, useMemo, useState } from 'react';
import { authorizationHeader } from '../auth/session';
import type { TemplateSummary } from '../records/api';
import { fetchEligibleParticipants, setParticipantSource, type ParticipantSource } from './api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const DEFAULT_SOURCE: ParticipantSource = { mode: 'all', participant_ids: [], municipality: '', previous_template_id: null, required_status: 'submitted' };

export function ParticipantSourcePanel({ template, onUpdate }: { template: TemplateSummary; onUpdate: (value: TemplateSummary) => void }) {
  const [source, setSource] = useState<ParticipantSource>(template.participant_source || DEFAULT_SOURCE);
  const [forms, setForms] = useState<TemplateSummary[]>([]);
  const [lookups, setLookups] = useState<Array<{ name: string; columns: string[] }>>([]);
  const [people, setPeople] = useState<Array<{ id: string; full_name: string; document_id?: string | null; external_code?: string | null; group_name?: string | null; status: string }>>([]);
  const [participantSearch, setParticipantSearch] = useState('');
  const [eligible, setEligible] = useState<number | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const activePeople = useMemo(() => people.filter((person) => person.status === 'active'), [people]);
  const visiblePeople = useMemo(() => activePeople.filter((person) => `${person.full_name} ${person.document_id || ''} ${person.external_code || ''} ${person.group_name || ''}`.toLocaleLowerCase().includes(participantSearch.trim().toLocaleLowerCase())), [activePeople, participantSearch]);

  function setVisibleSelection(selected: boolean) {
    const visibleIds = new Set(visiblePeople.map((person) => person.id));
    setSource((current) => ({ ...current, participant_ids: selected
      ? Array.from(new Set([...current.participant_ids, ...visibleIds]))
      : current.participant_ids.filter((id) => !visibleIds.has(id)) }));
  }

  useEffect(() => {
    void Promise.all([
      fetch(`${API_BASE_URL}/builder/templates/${template.project_id}`, { headers: authorizationHeader() }).then((response) => response.json()),
      fetch(`${API_BASE_URL}/participants/project/${template.project_id}`, { headers: authorizationHeader() }).then((response) => response.json()),
      fetch(`${API_BASE_URL}/form-lookups/templates/${template.id}`, { headers: authorizationHeader() }).then((response) => response.json()),
    ]).then(([templates, participants, files]) => { setForms(templates); setPeople(participants); setLookups(files); }).catch(() => setMessage('No fue posible cargar formularios, participantes o grupos Pull.'));
  }, [template.project_id]);

  useEffect(() => {
    const refreshLookups = () => { void fetch(`${API_BASE_URL}/form-lookups/templates/${template.id}`, { headers: authorizationHeader() }).then((response) => response.json()).then(setLookups).catch(() => undefined); };
    window.addEventListener('infomatt:pull-updated', refreshLookups);
    return () => window.removeEventListener('infomatt:pull-updated', refreshLookups);
  }, [template.id]);

  async function save() {
    if (source.mode === 'list' && source.participant_ids.length === 0) {
      setMessage('Selecciona al menos un participante antes de guardar.');
      return;
    }
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
      <option value="all">Todos los participantes</option><option value="list">Lista seleccionada</option><option value="group">Grupo de participantes</option><option value="filter">Municipio</option><option value="pull">Grupo Pull</option><option value="form">Formulario anterior completado</option>
    </select></label>
    {source.mode === 'list' && <div className="forms-participant-chooser"><strong>Elige los participantes de este formulario</strong><p>Marca cada persona que podrá responder. En la captura se elegirá a cuál de ellas corresponde cada respuesta.</p>{activePeople.length ? <><label>Buscar por nombre, documento, código o grupo<input type="search" value={participantSearch} onChange={(event) => setParticipantSearch(event.target.value)} placeholder="Buscar participante" /></label><div className="forms-participant-chooser-actions"><span>{source.participant_ids.length} seleccionado(s) · {visiblePeople.length} visible(s)</span><button type="button" onClick={() => setVisibleSelection(true)} disabled={!visiblePeople.length}>Seleccionar visibles</button><button type="button" onClick={() => setVisibleSelection(false)} disabled={!visiblePeople.length}>Quitar visibles</button></div><div className="forms-participant-options" role="group" aria-label="Participantes permitidos">{visiblePeople.map((person) => <label key={person.id}><input type="checkbox" checked={source.participant_ids.includes(person.id)} onChange={(event) => setSource((current) => ({ ...current, participant_ids: event.target.checked ? [...current.participant_ids, person.id] : current.participant_ids.filter((id) => id !== person.id) }))} /><span><strong>{person.full_name}</strong><small>{[person.document_id, person.external_code, person.group_name].filter(Boolean).join(' · ') || 'Sin identificador adicional'}</small></span></label>)}{!visiblePeople.length && <p>No hay participantes que coincidan con la búsqueda.</p>}</div></> : <p>No hay participantes activos en este proyecto. <a href="/participants">Agregar participantes</a> y vuelve a esta configuración.</p>}</div>}
    {source.mode === 'group' && <label>Grupo<select value={source.group_name || ''} onChange={(event) => setSource({ ...source, group_name: event.target.value })}><option value="">Selecciona un grupo</option>{Array.from(new Set(people.map((person) => person.group_name).filter((name): name is string => Boolean(name)))).sort().map((name) => <option key={name} value={name}>{name}</option>)}</select></label>}
    {source.mode === 'filter' && <label>Municipio<input value={source.municipality || ''} onChange={(event) => setSource({ ...source, municipality: event.target.value })} /></label>}
    {source.mode === 'form' && <><label>Formulario anterior<select value={source.previous_template_id || ''} onChange={(event) => setSource({ ...source, previous_template_id: event.target.value || null })}><option value="">Selecciona un formulario</option>{forms.filter((form) => form.id !== template.id).map((form) => <option key={form.id} value={form.id}>{form.name}</option>)}</select></label><label>Estado requerido<select value={source.required_status} onChange={(event) => setSource({ ...source, required_status: event.target.value })}><option value="submitted">Enviado</option><option value="completed">Completado</option><option value="approved">Aprobado</option></select></label></>}
    {source.mode === 'pull' && <><label>Grupo Pull<select value={source.pull_name || ''} onChange={(event) => setSource({ ...source, pull_name: event.target.value, pull_key_column: '' })}><option value="">Selecciona un CSV</option>{lookups.map((lookup) => <option key={lookup.name} value={lookup.name}>{lookup.name}.csv</option>)}</select></label><label>Columna de relación<select value={source.pull_key_column || ''} onChange={(event) => setSource({ ...source, pull_key_column: event.target.value })}><option value="">Selecciona una columna</option>{lookups.find((lookup) => lookup.name === source.pull_name)?.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label></>}
    <label>Llave para identificar al participante al capturar<select value={source.participant_key_field || 'external_code'} onChange={(event) => setSource({ ...source, participant_key_field: event.target.value as 'external_code' | 'document_id' })}><option value="document_id">Número de documento o cédula</option><option value="external_code">Código del participante</option></select></label>
    <button type="button" disabled={busy} onClick={() => void save()}>Guardar fuente</button>{eligible !== null && <p>{eligible} participante(s) elegibles actualmente.</p>}{message && <p role="status">{message}</p>}
  </div>;
}

