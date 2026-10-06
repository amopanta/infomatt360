import { useEffect, useMemo, useState } from 'react';
import { authorizationHeader } from '../auth/session';
import { hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchCaseAssignees } from '../participants/api';
import { fetchGestorTeamSummaries, type GestorTeamSummary } from '../teams/api';
import type { TemplateSummary } from '../records/api';
import { assignFormParticipant, bulkAssignFormParticipants, fetchFormAssignments, fetchFormCandidates, removeFormAssignment, setParticipantSource, type BulkAssignmentPreview, type FormAssignment, type FormCandidate, type ParticipantSource } from './api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const DEFAULT_SOURCE: ParticipantSource = { mode: 'all', access_mode: 'legacy', participant_ids: [], municipality: '', previous_template_id: null, required_status: 'submitted' };

export function ParticipantSourcePanel({ template, onUpdate }: { template: TemplateSummary; onUpdate: (value: TemplateSummary) => void }) {
  const [source, setSource] = useState<ParticipantSource>(template.participant_source || DEFAULT_SOURCE);
  const [forms, setForms] = useState<TemplateSummary[]>([]);
  const [lookups, setLookups] = useState<Array<{ name: string; columns: string[] }>>([]);
  const [people, setPeople] = useState<Array<{ id: string; full_name: string; document_id?: string | null; external_code?: string | null; group_name?: string | null; status: string }>>([]);
  const [participantSearch, setParticipantSearch] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [assignments, setAssignments] = useState<FormAssignment[]>([]);
  const [candidates, setCandidates] = useState<FormCandidate[]>([]);
  const [responsibles, setResponsibles] = useState<Array<{ id: string; full_name: string }>>([]);
  const [assignParticipantId, setAssignParticipantId] = useState('');
  const [assignResponsibleId, setAssignResponsibleId] = useState('');
  const [bulkMode, setBulkMode] = useState<'group' | 'team' | 'excel'>(source.mode === 'team' ? 'team' : 'group');
  const [teams, setTeams] = useState<GestorTeamSummary[]>([]);
  const [bulkTeamId, setBulkTeamId] = useState(source.team_id || '');
  const [bulkGroup, setBulkGroup] = useState(source.group_name || '');
  const [bulkFile, setBulkFile] = useState<File | null>(null);
  const [bulkPreview, setBulkPreview] = useState<BulkAssignmentPreview | null>(null);
  const canManageAssignments = hasAnyCurrentProjectPermission(['identity.users.manage']);
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
      fetchGestorTeamSummaries(template.project_id),
    ]).then(([templates, participants, files, teamRows]) => { setForms(templates); setPeople(participants); setLookups(files); setTeams(teamRows); }).catch(() => setMessage('No fue posible cargar formularios, participantes o equipos.'));
  }, [template.project_id]);

  async function refreshAssignments() {
    const [rows, peopleRows, userRows, teamRows] = await Promise.all([fetchFormAssignments(template.id), fetchFormCandidates(template.id), fetchCaseAssignees(template.project_id), fetchGestorTeamSummaries(template.project_id)]);
    setAssignments(rows); setCandidates(peopleRows); setResponsibles(userRows); setTeams(teamRows);
  }

  useEffect(() => {
    if (canManageAssignments) void refreshAssignments().catch(() => setMessage('No fue posible consultar las asignaciones del formulario.'));
  }, [template.id, template.project_id, canManageAssignments]);

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
      if (source.mode === 'group') setBulkGroup(source.group_name || '');
      if (source.mode === 'team') { setBulkMode('team'); setBulkTeamId(source.team_id || ''); }
      if (canManageAssignments) await refreshAssignments();
      setMessage('Fuente guardada. Se aplicará a las nuevas respuestas.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible guardar.'); }
    finally { setBusy(false); }
  }

  async function assign() {
    if (!assignParticipantId || !assignResponsibleId) { setMessage('Selecciona participante y responsable.'); return; }
    setBusy(true);
    try { await assignFormParticipant(template.id, assignParticipantId, assignResponsibleId); await refreshAssignments(); setAssignParticipantId(''); setMessage('Participante asignado al responsable.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible asignar.'); }
    finally { setBusy(false); }
  }

  async function remove(participantId: string) {
    setBusy(true);
    try { await removeFormAssignment(template.id, participantId); await refreshAssignments(); setMessage('Asignación retirada.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible quitar la asignación.'); }
    finally { setBusy(false); }
  }

  async function runBulk(previewOnly: boolean) {
    if (!assignResponsibleId) { setMessage('Selecciona primero el responsable.'); return; }
    if (bulkMode === 'group' && !bulkGroup) { setMessage('Selecciona el grupo que quieres asignar.'); return; }
    if (bulkMode === 'team' && !bulkTeamId) { setMessage('Selecciona un equipo de gestores.'); return; }
    if (bulkMode === 'excel' && !bulkFile) { setMessage('Selecciona un Excel con una columna documento o codigo.'); return; }
    setBusy(true); setMessage('');
    try {
      const result = await bulkAssignFormParticipants(template.id, { responsibleUserId: assignResponsibleId, mode: bulkMode, groupName: bulkGroup, teamId: bulkTeamId, file: bulkFile, previewOnly });
      setBulkPreview(result);
      if (!previewOnly) { await refreshAssignments(); setBulkPreview(null); setMessage(`${result.applied} participante(s) asignado(s) o reasignado(s).`); }
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible procesar la asignación masiva.'); }
    finally { setBusy(false); }
  }

  return <div className="forms-public-links"><h3>Fuente de participantes</h3><p>Define quién puede responder. La regla se verifica al guardar cada respuesta.</p>
    <label>Acceso al formulario<select value={source.access_mode || 'legacy'} onChange={(event) => setSource({ ...source, access_mode: event.target.value as ParticipantSource['access_mode'] })}><option value="legacy">Modo anterior (sin asignaciones individuales)</option><option value="open">Abierto: admite participantes nuevos con permiso</option><option value="closed">Cerrado: solo población previamente asignada</option></select></label>
    <label>Origen<select value={source.mode} onChange={(event) => setSource({ ...source, mode: event.target.value as ParticipantSource['mode'] })}>
      <option value="all">Todos los participantes</option><option value="list">Lista seleccionada</option><option value="group">Grupo de participantes importados</option><option value="team">Equipo de gestores</option><option value="filter">Municipio</option><option value="pull">Grupo Pull</option><option value="form">Formulario anterior completado</option>
    </select></label>
    {source.mode === 'list' && <div className="forms-participant-chooser"><strong>Elige los participantes de este formulario</strong><p>Marca cada persona que podrá responder. En la captura se elegirá a cuál de ellas corresponde cada respuesta.</p>{activePeople.length ? <><label>Buscar por nombre, documento, código o grupo<input type="search" value={participantSearch} onChange={(event) => setParticipantSearch(event.target.value)} placeholder="Buscar participante" /></label><div className="forms-participant-chooser-actions"><span>{source.participant_ids.length} seleccionado(s) · {visiblePeople.length} visible(s)</span><button type="button" onClick={() => setVisibleSelection(true)} disabled={!visiblePeople.length}>Seleccionar visibles</button><button type="button" onClick={() => setVisibleSelection(false)} disabled={!visiblePeople.length}>Quitar visibles</button></div><div className="forms-participant-options" role="group" aria-label="Participantes permitidos">{visiblePeople.map((person) => <label key={person.id}><input type="checkbox" checked={source.participant_ids.includes(person.id)} onChange={(event) => setSource((current) => ({ ...current, participant_ids: event.target.checked ? [...current.participant_ids, person.id] : current.participant_ids.filter((id) => id !== person.id) }))} /><span><strong>{person.full_name}</strong><small>{[person.document_id, person.external_code, person.group_name].filter(Boolean).join(' · ') || 'Sin identificador adicional'}</small></span></label>)}{!visiblePeople.length && <p>No hay participantes que coincidan con la búsqueda.</p>}</div></> : <p>No hay participantes activos en este proyecto. <a href="/participants">Agregar participantes</a> y vuelve a esta configuración.</p>}</div>}
    {source.mode === 'group' && <label>Grupo<select value={source.group_name || ''} onChange={(event) => setSource({ ...source, group_name: event.target.value })}><option value="">Selecciona un grupo</option>{Array.from(new Set(people.map((person) => person.group_name).filter((name): name is string => Boolean(name)))).sort().map((name) => <option key={name} value={name}>{name}</option>)}</select></label>}
    {source.mode === 'team' && <><fieldset><legend>Equipos de gestores asociados</legend><p>Puedes seleccionar varios equipos. Los participantes repetidos se cuentan una sola vez.</p>{teams.map((team) => { const selectedIds = source.team_ids?.length ? source.team_ids : source.team_id ? [source.team_id] : []; return <label key={team.id} className="forms-pull-choice"><input type="checkbox" checked={selectedIds.includes(team.id)} onChange={(event) => setSource((current) => { const ids = current.team_ids?.length ? current.team_ids : current.team_id ? [current.team_id] : []; return { ...current, team_id: null, team_ids: event.target.checked ? [...new Set([...ids, team.id])] : ids.filter((id) => id !== team.id) }; })} /> {team.name} · {team.participant_count} participantes · {team.user_count} gestores</label>; })}</fieldset><p>Guardar el origen define la población elegible. Después elige el responsable y confirma la asignación masiva para que el formulario aparezca en su escritorio.</p></>}
    {source.mode === 'filter' && <label>Municipio<input value={source.municipality || ''} onChange={(event) => setSource({ ...source, municipality: event.target.value })} /></label>}
    {source.mode === 'form' && <><label>Formulario anterior<select value={source.previous_template_id || ''} onChange={(event) => setSource({ ...source, previous_template_id: event.target.value || null })}><option value="">Selecciona un formulario</option>{forms.filter((form) => form.id !== template.id).map((form) => <option key={form.id} value={form.id}>{form.name}</option>)}</select></label><label>Estado requerido<select value={source.required_status} onChange={(event) => setSource({ ...source, required_status: event.target.value })}><option value="submitted">Enviado</option><option value="completed">Completado</option><option value="approved">Aprobado</option></select></label></>}
    {source.mode === 'pull' && <><label>Grupo Pull<select value={source.pull_name || ''} onChange={(event) => setSource({ ...source, pull_name: event.target.value, pull_key_column: '' })}><option value="">Selecciona un CSV</option>{lookups.map((lookup) => <option key={lookup.name} value={lookup.name}>{lookup.name}.csv</option>)}</select></label><label>Columna de relación<select value={source.pull_key_column || ''} onChange={(event) => setSource({ ...source, pull_key_column: event.target.value })}><option value="">Selecciona una columna</option>{lookups.find((lookup) => lookup.name === source.pull_name)?.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label></>}
    <label>Llave para identificar al participante al capturar<select value={source.participant_key_field || 'external_code'} onChange={(event) => setSource({ ...source, participant_key_field: event.target.value as 'external_code' | 'document_id' })}><option value="document_id">Número de documento o cédula</option><option value="external_code">Código del participante</option></select></label>
    <button type="button" disabled={busy} onClick={() => void save()}>Guardar fuente</button>{canManageAssignments && <p>{candidates.length} participante(s) disponibles en la fuente · {assignments.length} asignado(s) a responsables.</p>}{message && <p role="status">{message}</p>}
    {canManageAssignments && (source.access_mode === 'open' || source.access_mode === 'closed') && <section className="form-assignment-manager"><h4>Asignaciones por responsable</h4><p>Elige un responsable y asigna una persona, un grupo completo o una lista desde Excel.</p><label>Responsable<select value={assignResponsibleId} onChange={(event) => { setAssignResponsibleId(event.target.value); setBulkPreview(null); }}><option value="">Selecciona responsable</option>{responsibles.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}</select></label><details><summary>Asignar uno a uno</summary><div className="forms-participant-chooser-actions"><label>Participante<select value={assignParticipantId} onChange={(event) => setAssignParticipantId(event.target.value)}><option value="">Selecciona participante</option>{candidates.map((person) => <option key={person.id} value={person.id}>{person.full_name} · {person.document_id || person.external_code || 'Sin llave'}</option>)}</select></label><button type="button" disabled={busy || !assignParticipantId || !assignResponsibleId} onClick={() => void assign()}>Asignar participante</button></div></details><details open><summary>Asignar varios participantes</summary><div className="forms-participant-chooser-actions"><label>Método<select value={bulkMode} onChange={(event) => { setBulkMode(event.target.value as 'group' | 'team' | 'excel'); setBulkPreview(null); }}><option value="group">Grupo de importación</option><option value="team">Equipo de gestores</option><option value="excel">Lista desde Excel</option></select></label>{bulkMode === 'group' ? <label>Grupo<select value={bulkGroup} onChange={(event) => { setBulkGroup(event.target.value); setBulkPreview(null); }}><option value="">Selecciona grupo</option>{Array.from(new Set(activePeople.map((person) => person.group_name).filter((name): name is string => Boolean(name)))).sort().map((name) => <option key={name} value={name}>{name}</option>)}</select></label> : bulkMode === 'team' ? <label>Equipo<select value={bulkTeamId} onChange={(event) => { setBulkTeamId(event.target.value); setBulkPreview(null); }}><option value="">Selecciona equipo</option>{teams.map((team) => <option key={team.id} value={team.id}>{team.name} · {team.participant_count} participantes</option>)}</select></label> : <label>Archivo .xlsx o .csv<input type="file" accept=".xlsx,.csv" onChange={(event) => { setBulkFile(event.target.files?.[0] || null); setBulkPreview(null); }} /></label>}<button type="button" disabled={busy || !assignResponsibleId || (bulkMode === 'group' ? !bulkGroup : bulkMode === 'team' ? !bulkTeamId : !bulkFile)} onClick={() => void runBulk(true)}>Validar asignación</button></div>{bulkMode === 'excel' && <p>El archivo debe tener una sola columna llamada <strong>documento</strong> o <strong>codigo</strong>, y una fila por participante. Máximo 5000 filas y 5 MB.</p>}{bulkPreview && <div role="status"><p>{bulkPreview.selected} encontrados · {bulkPreview.to_assign} nuevos · {bulkPreview.to_reassign} a reasignar · {bulkPreview.already_assigned} ya asignados · {bulkPreview.protected} con respuesta o cerrados.</p>{bulkPreview.issues.length > 0 && <ul>{bulkPreview.issues.map((issue, index) => <li key={`${index}:${issue}`}>{issue}</li>)}</ul>}<button type="button" disabled={busy || bulkPreview.issues.length > 0 || bulkPreview.to_assign + bulkPreview.to_reassign === 0} onClick={() => void runBulk(false)}>Confirmar asignación masiva</button></div>}</details><div className="records-table-wrap"><table className="records-table"><thead><tr><th>Participante</th><th>Responsable</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{assignments.map((item) => <tr key={item.id}><td>{item.participant_name}</td><td>{item.responsible_name}</td><td>{item.status}</td><td><button type="button" disabled={busy} onClick={() => void remove(item.participant_id)}>Quitar</button></td></tr>)}</tbody></table></div></section>}
  </div>;
}

