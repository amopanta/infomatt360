import { useEffect, useMemo, useState } from 'react';
import { authorizationHeader } from '../auth/session';
import { hasAnyCurrentProjectPermission } from '../auth/session';
import { fetchCaseAssignees } from '../participants/api';
import { fetchGestorTeamSummaries, type GestorTeamSummary } from '../teams/api';
import type { TemplateSummary } from '../records/api';
import { assignFormParticipant, bulkAssignFormParticipants, fetchFormAssignments, fetchFormCandidates, removeFormAssignment, setParticipantSource, type BulkAssignmentPreview, type FormAssignment, type FormCandidate, type ParticipantSource } from './api';
import { useI18n } from '../../i18n';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const DEFAULT_SOURCE: ParticipantSource = { mode: 'all', access_mode: 'legacy', participant_ids: [], municipality: '', previous_template_id: null, required_status: 'submitted' };

export function ParticipantSourcePanel({ template, onUpdate }: { template: TemplateSummary; onUpdate: (value: TemplateSummary) => void }) {
  const { t } = useI18n();
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
    ]).then(([templates, participants, files, teamRows]) => { setForms(templates); setPeople(participants); setLookups(files); setTeams(teamRows); }).catch(() => setMessage(t('builder.participantSource.loadFailed')));
  }, [template.project_id]);

  async function refreshAssignments() {
    const [rows, peopleRows, userRows, teamRows] = await Promise.all([fetchFormAssignments(template.id), fetchFormCandidates(template.id), fetchCaseAssignees(template.project_id), fetchGestorTeamSummaries(template.project_id)]);
    setAssignments(rows); setCandidates(peopleRows); setResponsibles(userRows); setTeams(teamRows);
  }

  useEffect(() => {
    if (canManageAssignments) void refreshAssignments().catch(() => setMessage(t('builder.participantSource.assignmentsFailed')));
  }, [template.id, template.project_id, canManageAssignments]);

  useEffect(() => {
    const refreshLookups = () => { void fetch(`${API_BASE_URL}/form-lookups/templates/${template.id}`, { headers: authorizationHeader() }).then((response) => response.json()).then(setLookups).catch(() => undefined); };
    window.addEventListener('infomatt:pull-updated', refreshLookups);
    return () => window.removeEventListener('infomatt:pull-updated', refreshLookups);
  }, [template.id]);

  async function save() {
    if (source.mode === 'list' && source.participant_ids.length === 0) {
      setMessage(t('builder.participantSource.selectAtLeastOne'));
      return;
    }
    setBusy(true); setMessage('');
    try {
      const updated = await setParticipantSource(template.id, source);
      onUpdate(updated);
      if (source.mode === 'group') setBulkGroup(source.group_name || '');
      if (source.mode === 'team') { setBulkMode('team'); setBulkTeamId(source.team_id || ''); }
      if (canManageAssignments) await refreshAssignments();
      setMessage(t('builder.participantSource.sourceSaved'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('builder.participantSource.saveFailed')); }
    finally { setBusy(false); }
  }

  async function assign() {
    if (!assignParticipantId || !assignResponsibleId) { setMessage(t('builder.participantSource.selectResponsibleFirst')); return; }
    setBusy(true);
    try { await assignFormParticipant(template.id, assignParticipantId, assignResponsibleId); await refreshAssignments(); setAssignParticipantId(''); setMessage(t('builder.participantSource.assignedToResponsible')); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('builder.participantSource.assignFailed')); }
    finally { setBusy(false); }
  }

  async function remove(participantId: string) {
    setBusy(true);
    try { await removeFormAssignment(template.id, participantId); await refreshAssignments(); setMessage(t('builder.participantSource.assignmentRemoved')); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('builder.participantSource.removeFailed')); }
    finally { setBusy(false); }
  }

  async function runBulk(previewOnly: boolean) {
    if (!assignResponsibleId) { setMessage(t('builder.participantSource.selectResponsibleFirst')); return; }
    if (bulkMode === 'group' && !bulkGroup) { setMessage(t('builder.participantSource.selectGroupFirst')); return; }
    if (bulkMode === 'team' && !bulkTeamId) { setMessage(t('builder.participantSource.selectTeamFirst')); return; }
    if (bulkMode === 'excel' && !bulkFile) { setMessage(t('builder.participantSource.selectExcelFirst')); return; }
    setBusy(true); setMessage('');
    try {
      const result = await bulkAssignFormParticipants(template.id, { responsibleUserId: assignResponsibleId, mode: bulkMode, groupName: bulkGroup, teamId: bulkTeamId, file: bulkFile, previewOnly });
      setBulkPreview(result);
      if (!previewOnly) { await refreshAssignments(); setBulkPreview(null); setMessage(t('builder.participantSource.bulkSuccess', { count: result.applied })); }
    } catch (error) { setMessage(error instanceof Error ? error.message : t('builder.participantSource.bulkFailed')); }
    finally { setBusy(false); }
  }

  return <div className="forms-public-links"><h3>{t('builder.participantSource.title')}</h3><p>{t('builder.participantSource.description')}</p>
    <label>{t('builder.participantSource.formAccess')}<select value={source.access_mode || 'legacy'} onChange={(event) => setSource({ ...source, access_mode: event.target.value as ParticipantSource['access_mode'] })}><option value="legacy">{t('builder.participantSource.legacyMode')}</option><option value="open">{t('builder.participantSource.openMode')}</option><option value="closed">{t('builder.participantSource.closedMode')}</option></select></label>
    <label>{t('builder.participantSource.sourceLabel')}<select value={source.mode} onChange={(event) => setSource({ ...source, mode: event.target.value as ParticipantSource['mode'] })}>
      <option value="all">{t('builder.participantSource.allParticipants')}</option><option value="list">{t('builder.participantSource.selectedList')}</option><option value="group">{t('builder.participantSource.participantGroup')}</option><option value="team">{t('builder.participantSource.gestorTeam')}</option><option value="filter">{t('builder.participantSource.municipalityFilter')}</option><option value="pull">{t('builder.participantSource.pullGroup')}</option><option value="form">{t('builder.participantSource.previousForm')}</option>
    </select></label>
    {source.mode === 'list' && <div className="forms-participant-chooser"><strong>{t('builder.participantSource.chooseParticipants')}</strong><p>{t('builder.participantSource.chooseParticipantsDesc')}</p>{activePeople.length ? <><label>{t('builder.participantSource.searchByNameDoc')}<input type="search" value={participantSearch} onChange={(event) => setParticipantSearch(event.target.value)} placeholder={t('builder.participantSource.searchPlaceholder')} /></label><div className="forms-participant-chooser-actions"><span>{t('builder.participantSource.selectedCount', { selected: source.participant_ids.length, visible: visiblePeople.length })}</span><button type="button" onClick={() => setVisibleSelection(true)} disabled={!visiblePeople.length}>{t('builder.participantSource.selectVisible')}</button><button type="button" onClick={() => setVisibleSelection(false)} disabled={!visiblePeople.length}>{t('builder.participantSource.removeVisible')}</button></div><div className="forms-participant-options" role="group" aria-label={t('builder.participantSource.allowedParticipantsAria')}>{visiblePeople.map((person) => <label key={person.id}><input type="checkbox" checked={source.participant_ids.includes(person.id)} onChange={(event) => setSource((current) => ({ ...current, participant_ids: event.target.checked ? [...current.participant_ids, person.id] : current.participant_ids.filter((id) => id !== person.id) }))} /><span><strong>{person.full_name}</strong><small>{[person.document_id, person.external_code, person.group_name].filter(Boolean).join(' · ') || t('builder.participantSource.noAdditionalId')}</small></span></label>)}{!visiblePeople.length && <p>{t('builder.participantSource.noMatchingParticipants')}</p>}</div></> : <p>{t('builder.participantSource.noActiveParticipants')} <a href="/participants">{t('builder.participantSource.addParticipantsLink')}</a> {t('builder.participantSource.returnToConfig')}</p>}</div>}
    {source.mode === 'group' && <label>{t('builder.participantSource.groupLabel')}<select value={source.group_name || ''} onChange={(event) => setSource({ ...source, group_name: event.target.value })}><option value="">{t('builder.participantSource.selectGroup')}</option>{Array.from(new Set(people.map((person) => person.group_name).filter((name): name is string => Boolean(name)))).sort().map((name) => <option key={name} value={name}>{name}</option>)}</select></label>}
    {source.mode === 'team' && <><fieldset><legend>{t('builder.participantSource.teamsFieldset')}</legend><p>{t('builder.participantSource.teamsHint')}</p>{teams.map((team) => { const selectedIds = source.team_ids?.length ? source.team_ids : source.team_id ? [source.team_id] : []; return <label key={team.id} className="forms-pull-choice"><input type="checkbox" checked={selectedIds.includes(team.id)} onChange={(event) => setSource((current) => { const ids = current.team_ids?.length ? current.team_ids : current.team_id ? [current.team_id] : []; return { ...current, team_id: null, team_ids: event.target.checked ? [...new Set([...ids, team.id])] : ids.filter((id) => id !== team.id) }; })} /> {t('builder.participantSource.teamSummary', { name: team.name, participantCount: team.participant_count, userCount: team.user_count })}</label>; })}</fieldset><p>{t('builder.participantSource.saveSourceHint')}</p></>}
    {source.mode === 'filter' && <label>{t('builder.participantSource.municipalityLabel')}<input value={source.municipality || ''} onChange={(event) => setSource({ ...source, municipality: event.target.value })} /></label>}
    {source.mode === 'form' && <><label>{t('builder.participantSource.previousFormLabel')}<select value={source.previous_template_id || ''} onChange={(event) => setSource({ ...source, previous_template_id: event.target.value || null })}><option value="">{t('builder.participantSource.selectForm')}</option>{forms.filter((form) => form.id !== template.id).map((form) => <option key={form.id} value={form.id}>{form.name}</option>)}</select></label><label>{t('builder.participantSource.requiredStatus')}<select value={source.required_status} onChange={(event) => setSource({ ...source, required_status: event.target.value })}><option value="submitted">{t('builder.participantSource.statusSubmitted')}</option><option value="completed">{t('builder.participantSource.statusCompleted')}</option><option value="approved">{t('builder.participantSource.statusApproved')}</option></select></label></>}
    {source.mode === 'pull' && <><label>{t('builder.participantSource.pullGroupLabel')}<select value={source.pull_name || ''} onChange={(event) => setSource({ ...source, pull_name: event.target.value, pull_key_column: '' })}><option value="">{t('builder.participantSource.selectCsv')}</option>{lookups.map((lookup) => <option key={lookup.name} value={lookup.name}>{lookup.name}.csv</option>)}</select></label><label>{t('builder.participantSource.relationColumn')}<select value={source.pull_key_column || ''} onChange={(event) => setSource({ ...source, pull_key_column: event.target.value })}><option value="">{t('builder.participantSource.selectColumn')}</option>{lookups.find((lookup) => lookup.name === source.pull_name)?.columns.map((column) => <option key={column} value={column}>{column}</option>)}</select></label></>}
    <label>{t('builder.participantSource.participantKey')}<select value={source.participant_key_field || 'external_code'} onChange={(event) => setSource({ ...source, participant_key_field: event.target.value as 'external_code' | 'document_id' })}><option value="document_id">{t('builder.participantSource.documentNumber')}</option><option value="external_code">{t('builder.participantSource.participantCode')}</option></select></label>
    <button type="button" disabled={busy} onClick={() => void save()}>{t('builder.participantSource.saveSource')}</button>{canManageAssignments && <p>{t('builder.participantSource.candidatesCount', { candidates: candidates.length, assignments: assignments.length })}</p>}{message && <p role="status">{message}</p>}
    {canManageAssignments && (source.access_mode === 'open' || source.access_mode === 'closed') && <section className="form-assignment-manager"><h4>{t('builder.participantSource.assignmentTitle')}</h4><p>{t('builder.participantSource.assignmentDesc')}</p><label>{t('builder.participantSource.responsibleLabel')}<select value={assignResponsibleId} onChange={(event) => { setAssignResponsibleId(event.target.value); setBulkPreview(null); }}><option value="">{t('builder.participantSource.selectResponsible')}</option>{responsibles.map((person) => <option key={person.id} value={person.id}>{person.full_name}</option>)}</select></label><details><summary>{t('builder.participantSource.assignOneByOne')}</summary><div className="forms-participant-chooser-actions"><label>{t('builder.participantSource.participantLabel')}<select value={assignParticipantId} onChange={(event) => setAssignParticipantId(event.target.value)}><option value="">{t('builder.participantSource.selectParticipant')}</option>{candidates.map((person) => <option key={person.id} value={person.id}>{person.full_name} · {person.document_id || person.external_code || t('builder.participantSource.noKey')}</option>)}</select></label><button type="button" disabled={busy || !assignParticipantId || !assignResponsibleId} onClick={() => void assign()}>{t('builder.participantSource.assignParticipant')}</button></div></details><details open><summary>{t('builder.participantSource.assignMultiple')}</summary><div className="forms-participant-chooser-actions"><label>{t('builder.participantSource.methodLabel')}<select value={bulkMode} onChange={(event) => { setBulkMode(event.target.value as 'group' | 'team' | 'excel'); setBulkPreview(null); }}><option value="group">{t('builder.participantSource.importGroupOption')}</option><option value="team">{t('builder.participantSource.gestorTeamOption')}</option><option value="excel">{t('builder.participantSource.excelListOption')}</option></select></label>{bulkMode === 'group' ? <label>{t('builder.participantSource.groupLabel')}<select value={bulkGroup} onChange={(event) => { setBulkGroup(event.target.value); setBulkPreview(null); }}><option value="">{t('builder.participantSource.selectGroup')}</option>{Array.from(new Set(activePeople.map((person) => person.group_name).filter((name): name is string => Boolean(name)))).sort().map((name) => <option key={name} value={name}>{name}</option>)}</select></label> : bulkMode === 'team' ? <label>{t('builder.participantSource.selectTeam')}<select value={bulkTeamId} onChange={(event) => { setBulkTeamId(event.target.value); setBulkPreview(null); }}><option value="">{t('builder.participantSource.selectTeam')}</option>{teams.map((team) => <option key={team.id} value={team.id}>{t('builder.participantSource.teamParticipants', { name: team.name, count: team.participant_count })}</option>)}</select></label> : <label>{t('builder.participantSource.excelFile')}<input type="file" accept=".xlsx,.csv" onChange={(event) => { setBulkFile(event.target.files?.[0] || null); setBulkPreview(null); }} /></label>}<button type="button" disabled={busy || !assignResponsibleId || (bulkMode === 'group' ? !bulkGroup : bulkMode === 'team' ? !bulkTeamId : !bulkFile)} onClick={() => void runBulk(true)}>{t('builder.participantSource.validateAssignment')}</button></div>{bulkMode === 'excel' && <p dangerouslySetInnerHTML={{ __html: t('builder.participantSource.excelHint') }} />}{bulkPreview && <div role="status"><p>{t('builder.participantSource.bulkPreviewSummary', { selected: bulkPreview.selected, toAssign: bulkPreview.to_assign, toReassign: bulkPreview.to_reassign, alreadyAssigned: bulkPreview.already_assigned, protected: bulkPreview.protected })}</p>{bulkPreview.issues.length > 0 && <ul>{bulkPreview.issues.map((issue, index) => <li key={`${index}:${issue}`}>{issue}</li>)}</ul>}<button type="button" disabled={busy || bulkPreview.issues.length > 0 || bulkPreview.to_assign + bulkPreview.to_reassign === 0} onClick={() => void runBulk(false)}>{t('builder.participantSource.confirmBulkAssignment')}</button></div>}</details><div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('builder.participantSource.columnParticipant')}</th><th>{t('builder.participantSource.columnResponsible')}</th><th>{t('builder.participantSource.columnStatus')}</th><th>{t('builder.participantSource.columnAction')}</th></tr></thead><tbody>{assignments.map((item) => <tr key={item.id}><td>{item.participant_name}</td><td>{item.responsible_name}</td><td>{item.status}</td><td><button type="button" disabled={busy} onClick={() => void remove(item.participant_id)}>{t('builder.participantSource.removeAction')}</button></td></tr>)}</tbody></table></div></section>}
  </div>;
}
