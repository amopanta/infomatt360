import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { addGestorTeamMember, bulkImportGestorTeams, createGestorTeam, deleteGestorTeam, downloadGestorTeamTemplate, fetchGestorTeamSummaries, removeGestorTeamMember, renameGestorTeam, searchGestorTeamMembers, type GestorTeamSummary, type TeamBulkPreview, type TeamSearchResult } from './api';

export function TeamsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) || '';
  const [teams, setTeams] = useState<GestorTeamSummary[]>([]);
  const [selectedId, setSelectedId] = useState('');
  const [newName, setNewName] = useState('');
  const [name, setName] = useState('');
  const [kind, setKind] = useState<'gestor' | 'participante'>('gestor');
  const [search, setSearch] = useState('');
  const [teamSearch, setTeamSearch] = useState('');
  const [results, setResults] = useState<TeamSearchResult[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TeamBulkPreview | null>(null);
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const selected = teams.find((team) => team.id === selectedId);
  const visibleTeams = teams.filter((team) => team.name.toLocaleLowerCase().includes(teamSearch.trim().toLocaleLowerCase()));

  async function refreshTeams() { setTeams(await fetchGestorTeamSummaries(projectId)); }
  useEffect(() => { if (projectId) void refreshTeams().catch((error: Error) => setMessage(error.message)); }, [projectId]);
  useEffect(() => { setName(selected?.name || ''); }, [selectedId, selected?.name]);
  useEffect(() => {
    if (!selectedId) { setResults([]); return; }
    const timer = window.setTimeout(() => {
      void searchGestorTeamMembers(selectedId, kind, search).then(setResults).catch((error: Error) => setMessage(error.message));
    }, 300);
    return () => window.clearTimeout(timer);
  }, [selectedId, kind, search]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true); setMessage('');
    try { await action(); await refreshTeams(); setMessage(success); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible completar la operación.'); }
    finally { setBusy(false); }
  }
  async function create() {
    if (!newName.trim()) return;
    await run(async () => { const team = await createGestorTeam(projectId, newName.trim()); setSelectedId(team.id); setNewName(''); }, 'Equipo creado.');
  }
  async function toggle(person: TeamSearchResult) {
    if (!selected) return;
    setBusy(true); setMessage('');
    try {
      if (person.selected) await removeGestorTeamMember(selected.id, kind, person.id);
      else await addGestorTeamMember(selected.id, kind, person.id);
      setResults((current) => current.map((item) => item.id === person.id ? { ...item, selected: !person.selected } : item));
      await refreshTeams();
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el integrante.'); }
    finally { setBusy(false); }
  }
  async function validateFile(previewOnly: boolean) {
    if (!file) return;
    setBusy(true); setMessage('');
    try {
      const result = await bulkImportGestorTeams(projectId, file, previewOnly);
      setPreview(result);
      if (!previewOnly && !result.issues.length) { await refreshTeams(); setMessage(`${result.applied} integrantes agregados.`); setPreview(null); setFile(null); }
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible procesar el archivo.'); }
    finally { setBusy(false); }
  }

  return <AppShell title="Equipos de gestores"><main className="teams-page">
    <h1>Equipos de gestores</h1><p>Asigna usuarios y participantes a equipos. Estos equipos son distintos del grupo usado al importar participantes. Pertenecer a un equipo no concede acceso automático a formularios.</p>
    <section className="teams-card"><h2>Crear equipo</h2><div className="teams-inline"><input aria-label="Nombre del equipo" placeholder="Nombre del equipo" value={newName} onChange={(event) => setNewName(event.target.value)} /><button type="button" disabled={busy || !newName.trim()} onClick={() => void create()}>Crear equipo</button></div></section>
    <section className="teams-card"><h2>Asignación masiva desde Excel o CSV</h2><p>Una fila por integrante. Columnas: <strong>equipo, tipo, identificador</strong>. Usa <strong>gestor</strong> con correo o documento y <strong>participante</strong> con documento o código. Un archivo puede crear varios equipos y asignar miles de integrantes.</p>
      <div className="teams-inline"><button type="button" onClick={() => void downloadGestorTeamTemplate(projectId).catch((error: Error) => setMessage(error.message))}>Descargar plantilla</button><input type="file" aria-label="Archivo de equipos" accept=".xlsx,.csv" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); }} /><button type="button" disabled={busy || !file} onClick={() => void validateFile(true)}>Validar archivo</button></div>
      {preview && <div role="status"><p>{preview.rows} filas · {preview.teams_to_create} equipos nuevos · {preview.new_members} integrantes nuevos · {preview.already_members} ya vinculados.</p>{preview.issues.length > 0 && <ul>{preview.issues.map((issue, index) => <li key={`${index}-${issue}`}>{issue}</li>)}</ul>}<button type="button" disabled={busy || preview.issues.length > 0 || (preview.new_members === 0 && preview.teams_to_create === 0)} onClick={() => void validateFile(false)}>Confirmar carga masiva</button></div>}
    </section>
    <div className="teams-layout"><section className="teams-card"><h2>Equipos del proyecto</h2><label>Buscar equipo<input type="search" value={teamSearch} onChange={(event) => setTeamSearch(event.target.value)} placeholder="Nombre del equipo" /></label><p>{visibleTeams.length} de {teams.length} equipos</p>{visibleTeams.length ? visibleTeams.map((team) => <button type="button" className={`teams-item ${selectedId === team.id ? 'selected' : ''}`} key={team.id} onClick={() => setSelectedId(team.id)}>{team.name}<small>{team.user_count} gestores · {team.participant_count} participantes</small></button>) : <p>{teams.length ? 'No hay equipos que coincidan con la búsqueda.' : 'No hay equipos creados.'}</p>}</section>
      {selected && <section className="teams-card"><h2>Asignación individual: {selected.name}</h2><label>Nombre del equipo<input value={name} onChange={(event) => setName(event.target.value)} /></label><div className="teams-inline"><button type="button" disabled={busy || !name.trim() || name.trim() === selected.name} onClick={() => void run(() => renameGestorTeam(selected.id, name.trim()), 'Equipo renombrado.')}>Guardar nombre</button><button type="button" disabled={busy} onClick={() => { if (window.confirm(`¿Eliminar el equipo ${selected.name}?`)) void run(async () => { await deleteGestorTeam(selected.id); setSelectedId(''); }, 'Equipo eliminado.'); }}>Eliminar equipo</button></div>
        <div className="teams-inline"><label>Integrante<select value={kind} onChange={(event) => setKind(event.target.value as 'gestor' | 'participante')}><option value="gestor">Gestor</option><option value="participante">Participante</option></select></label><label>Buscar<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Nombre, correo, documento o código" /></label></div><p>Se muestran hasta 50 coincidencias. Busca para encontrar otros integrantes.</p>
        <div className="teams-options teams-people">{results.map((person) => <label key={person.id}><input type="checkbox" disabled={busy} checked={person.selected} onChange={() => void toggle(person)} /><span>{person.name}<small>{person.identifier}</small></span></label>)}{!results.length && <p>No hay coincidencias.</p>}</div>
      </section>}
    </div>{message && <p role="status">{message}</p>}
  </main></AppShell>;
}

