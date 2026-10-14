import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { addGestorTeamMember, bulkImportGestorTeams, createGestorTeam, deleteGestorTeam, downloadGestorTeamTemplate, fetchGestorTeamSummaries, removeGestorTeamMember, renameGestorTeam, searchGestorTeamMembers, type GestorTeamSummary, type TeamBulkPreview, type TeamSearchResult } from './api';

export function TeamsApp() {
  const { t } = useI18n();
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
    catch (error) { setMessage(error instanceof Error ? error.message : t('teams.errorOperation')); }
    finally { setBusy(false); }
  }
  async function create() {
    if (!newName.trim()) return;
    await run(async () => { const team = await createGestorTeam(projectId, newName.trim()); setSelectedId(team.id); setNewName(''); }, t('teams.teamCreated'));
  }
  async function toggle(person: TeamSearchResult) {
    if (!selected) return;
    setBusy(true); setMessage('');
    try {
      if (person.selected) await removeGestorTeamMember(selected.id, kind, person.id);
      else await addGestorTeamMember(selected.id, kind, person.id);
      setResults((current) => current.map((item) => item.id === person.id ? { ...item, selected: !person.selected } : item));
      await refreshTeams();
    } catch (error) { setMessage(error instanceof Error ? error.message : t('teams.errorMember')); }
    finally { setBusy(false); }
  }
  async function validateFile(previewOnly: boolean) {
    if (!file) return;
    setBusy(true); setMessage('');
    try {
      const result = await bulkImportGestorTeams(projectId, file, previewOnly);
      setPreview(result);
      if (!previewOnly && !result.issues.length) { await refreshTeams(); setMessage(t('teams.bulkApplied', { count: result.applied })); setPreview(null); setFile(null); }
    } catch (error) { setMessage(error instanceof Error ? error.message : t('teams.errorFile')); }
    finally { setBusy(false); }
  }

  return <AppShell title={t('teams.title')}><main className="teams-page">
    <h1>{t('teams.title')}</h1><p>{t('teams.description')}</p>
    <section className="teams-card"><h2>{t('teams.createTeam')}</h2><div className="teams-inline"><input aria-label={t('teams.teamNameLabel')} placeholder={t('teams.teamNamePlaceholder')} value={newName} onChange={(event) => setNewName(event.target.value)} /><button type="button" disabled={busy || !newName.trim()} onClick={() => void create()}>{t('teams.createTeam')}</button></div></section>
    <section className="teams-card"><h2>{t('teams.bulkTitle')}</h2><p dangerouslySetInnerHTML={{ __html: t('teams.bulkDescription') }} />
      <div className="teams-inline"><button type="button" onClick={() => void downloadGestorTeamTemplate(projectId).catch((error: Error) => setMessage(error.message))}>{t('teams.downloadTemplate')}</button><input type="file" aria-label={t('teams.teamFileLabel')} accept=".xlsx,.csv" onChange={(event) => { setFile(event.target.files?.[0] || null); setPreview(null); }} /><button type="button" disabled={busy || !file} onClick={() => void validateFile(true)}>{t('teams.validateFile')}</button></div>
      {preview && <div role="status"><p>{t('teams.previewSummary', { rows: preview.rows, teamsToCreate: preview.teams_to_create, newMembers: preview.new_members, alreadyMembers: preview.already_members })}</p>{preview.issues.length > 0 && <ul>{preview.issues.map((issue, index) => <li key={`${index}-${issue}`}>{issue}</li>)}</ul>}<button type="button" disabled={busy || preview.issues.length > 0 || (preview.new_members === 0 && preview.teams_to_create === 0)} onClick={() => void validateFile(false)}>{t('teams.confirmBulk')}</button></div>}
    </section>
    <div className="teams-layout"><section className="teams-card"><h2>{t('teams.projectTeams')}</h2><label>{t('teams.searchTeam')}<input type="search" value={teamSearch} onChange={(event) => setTeamSearch(event.target.value)} placeholder={t('teams.teamNamePlaceholder')} /></label><p>{t('teams.teamsCount', { visible: visibleTeams.length, total: teams.length })}</p>{visibleTeams.length ? visibleTeams.map((team) => <button type="button" className={`teams-item ${selectedId === team.id ? 'selected' : ''}`} key={team.id} onClick={() => setSelectedId(team.id)}>{team.name}<small>{t('teams.teamSummary', { userCount: team.user_count, participantCount: team.participant_count })}</small></button>) : <p>{teams.length ? t('teams.noTeamsMatch') : t('teams.noTeamsCreated')}</p>}</section>
      {selected && <section className="teams-card"><h2>{t('teams.individualAssignment', { name: selected.name })}</h2><label>{t('teams.teamNameLabel')}<input value={name} onChange={(event) => setName(event.target.value)} /></label><div className="teams-inline"><button type="button" disabled={busy || !name.trim() || name.trim() === selected.name} onClick={() => void run(() => renameGestorTeam(selected.id, name.trim()), t('teams.teamRenamed'))}>{t('teams.saveName')}</button><button type="button" disabled={busy} onClick={() => { if (window.confirm(t('teams.confirmDelete', { name: selected.name }))) void run(async () => { await deleteGestorTeam(selected.id); setSelectedId(''); }, t('teams.teamDeleted')); }}>{t('teams.deleteTeam')}</button></div>
        <div className="teams-inline"><label>{t('teams.memberType')}<select value={kind} onChange={(event) => setKind(event.target.value as 'gestor' | 'participante')}><option value="gestor">{t('teams.gestorOption')}</option><option value="participante">{t('teams.participantOption')}</option></select></label><label>{t('teams.searchLabel')}<input type="search" value={search} onChange={(event) => setSearch(event.target.value)} placeholder={t('teams.searchPlaceholder')} /></label></div><p>{t('teams.searchHint')}</p>
        <div className="teams-options teams-people">{results.map((person) => <label key={person.id}><input type="checkbox" disabled={busy} checked={person.selected} onChange={() => void toggle(person)} /><span>{person.name}<small>{person.identifier}</small></span></label>)}{!results.length && <p>{t('teams.noMatches')}</p>}</div>
      </section>}
    </div>{message && <p role="status">{message}</p>}
  </main></AppShell>;
}
