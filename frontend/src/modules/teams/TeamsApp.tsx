import { useEffect, useMemo, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchCaseAssignees, fetchProjectParticipants, type CaseAssignee, type Participant } from '../participants/api';
import { createGestorTeam, deleteGestorTeam, fetchGestorTeams, renameGestorTeam, saveGestorTeamMembers, type GestorTeam } from './api';

export function TeamsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) || '';
  const [teams, setTeams] = useState<GestorTeam[]>([]);
  const [users, setUsers] = useState<CaseAssignee[]>([]);
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [name, setName] = useState('');
  const [newName, setNewName] = useState('');
  const [userIds, setUserIds] = useState<string[]>([]);
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const selected = teams.find((team) => team.id === selectedId);
  const visible = useMemo(() => participants.filter((person) => person.status === 'active' &&
    `${person.full_name} ${person.document_id || ''} ${person.external_code || ''} ${person.group_name || ''}`.toLocaleLowerCase().includes(search.toLocaleLowerCase())), [participants, search]);

  async function reload() {
    const [teamRows, userRows, peopleRows] = await Promise.all([fetchGestorTeams(projectId), fetchCaseAssignees(projectId), fetchProjectParticipants(projectId)]);
    setTeams(teamRows); setUsers(userRows); setParticipants(peopleRows);
  }
  useEffect(() => { if (projectId) void reload().catch((error: Error) => setMessage(error.message)); }, [projectId]);
  useEffect(() => {
    const team = teams.find((row) => row.id === selectedId);
    setName(team?.name || ''); setUserIds(team?.user_ids || []); setParticipantIds(team?.participant_ids || []);
  }, [selectedId, teams]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setMessage('');
    try { await action(); await reload(); setMessage(success); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible completar la operación.'); }
    finally { setBusy(false); }
  }
  async function create() {
    if (!newName.trim()) return;
    await run(async () => { const team = await createGestorTeam(projectId, newName.trim()); setSelectedId(team.id); setNewName(''); }, 'Equipo creado. Ahora agrega gestores y participantes.');
  }
  function toggle(id: string, values: string[], setter: (next: string[]) => void) {
    setter(values.includes(id) ? values.filter((value) => value !== id) : [...values, id]);
  }
  function selectVisible(add: boolean) {
    const ids = new Set(visible.map((person) => person.id));
    setParticipantIds((current) => add ? Array.from(new Set([...current, ...ids])) : current.filter((id) => !ids.has(id)));
  }

  return <AppShell title="Equipos de gestores"><main className="teams-page">
    <h1>Equipos de gestores</h1><p>Organiza usuarios y participantes en equipos. El grupo de importación de participantes se conserva por separado. Para diligenciar un formulario debes asignarlo a un responsable.</p>
    <section className="teams-card"><h2>Crear equipo</h2><div className="teams-inline"><input aria-label="Nombre del equipo" placeholder="Nombre del equipo" value={newName} onChange={(event) => setNewName(event.target.value)} /><button type="button" disabled={busy || !newName.trim()} onClick={() => void create()}>Crear equipo</button></div></section>
    <div className="teams-layout"><section className="teams-card"><h2>Equipos del proyecto</h2>{teams.length ? teams.map((team) => <button type="button" className={`teams-item ${selectedId === team.id ? 'selected' : ''}`} key={team.id} onClick={() => setSelectedId(team.id)}>{team.name}<small>{team.user_ids.length} gestores · {team.participant_ids.length} participantes</small></button>) : <p>No hay equipos creados.</p>}</section>
    {selected && <section className="teams-card"><h2>Integrantes de {selected.name}</h2><label>Nombre del equipo<input value={name} onChange={(event) => setName(event.target.value)} /></label>
      <h3>Gestores del equipo</h3><div className="teams-options">{users.map((person) => <label key={person.id}><input type="checkbox" checked={userIds.includes(person.id)} onChange={() => toggle(person.id, userIds, setUserIds)} />{person.full_name}</label>)}</div>
      <h3>Participantes del equipo</h3><input type="search" aria-label="Buscar participantes" placeholder="Buscar nombre, documento, código o grupo de importación" value={search} onChange={(event) => setSearch(event.target.value)} /><div className="teams-inline"><span>{participantIds.length} seleccionados · {visible.length} visibles</span><button type="button" onClick={() => selectVisible(true)} disabled={!visible.length}>Seleccionar visibles</button><button type="button" onClick={() => selectVisible(false)} disabled={!visible.length}>Quitar visibles</button></div>
      <div className="teams-options teams-people">{visible.map((person) => <label key={person.id}><input type="checkbox" checked={participantIds.includes(person.id)} onChange={() => toggle(person.id, participantIds, setParticipantIds)} /><span>{person.full_name}<small>{person.document_id || person.external_code || 'Sin documento'} · Grupo de importación: {person.group_name || 'Ninguno'}</small></span></label>)}</div>
      <div className="teams-inline"><button type="button" disabled={busy || !name.trim()} onClick={() => void run(async () => { if (name.trim() !== selected.name) await renameGestorTeam(selected.id, name.trim()); await saveGestorTeamMembers(selected.id, userIds, participantIds); }, 'Equipo e integrantes guardados.')}>Guardar equipo</button><button type="button" disabled={busy} onClick={() => { if (window.confirm(`¿Eliminar el equipo ${selected.name}?`)) void run(async () => { await deleteGestorTeam(selected.id); setSelectedId(''); }, 'Equipo eliminado.'); }}>Eliminar equipo</button></div>
    </section>}</div>{message && <p role="status">{message}</p>}
  </main></AppShell>;
}
