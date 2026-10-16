import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { assignParticipantGroup, assignTerritory, createParticipantCase, deleteParticipantGroup, fetchCaseAssignees, fetchCaseEvents, fetchParticipant, fetchParticipantActivities, fetchParticipantCases, fetchParticipantHistory, fetchProjectParticipants, fetchProjectSchedule, fetchTerritories, removeTerritory, setParticipantGroupStatus, updateParticipantCase } from './api';
import type { CaseAssignee, CaseEvent, Participant, ParticipantActivity, ParticipantCase, ParticipantHistoryItem, ScheduledCase, UserTerritory } from './api';

function participantIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[0] === 'participants' ? parts[1] ?? '' : '';
}

export function ParticipantsApp() {
  const participantId = participantIdFromPath();
  return participantId ? <ParticipantDetail participantId={participantId} /> : <ParticipantList />;
}

function ParticipantList() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [query, setQuery] = useState('');
  const [groupFilter, setGroupFilter] = useState('');
  const [editingGroupId, setEditingGroupId] = useState('');
  const [groupDraft, setGroupDraft] = useState('');
  const [message, setMessage] = useState(t('participants.loadingParticipants'));
  const [territories, setTerritories] = useState<UserTerritory[]>([]);
  const [assignees, setAssignees] = useState<CaseAssignee[]>([]);
  const [territoryUser, setTerritoryUser] = useState('');
  const [department, setDepartment] = useState('');
  const [municipality, setMunicipality] = useState('');
  const [schedule, setSchedule] = useState<ScheduledCase[]>([]);
  const [scheduleOpen, setScheduleOpen] = useState(false);

  const statusLabels: Record<string, string> = {
    draft: t('participants.statusLabels.draft'), submitted: t('participants.statusLabels.submitted'), under_review: t('participants.statusLabels.under_review'),
    tech_approved: t('participants.statusLabels.tech_approved'), coordinator_approved: t('participants.statusLabels.coordinator_approved'),
    returned: t('participants.statusLabels.returned'), corrected: t('participants.statusLabels.corrected'), approved: t('participants.statusLabels.approved'),
    rejected: t('participants.statusLabels.rejected'), cancelled: t('participants.statusLabels.cancelled'), archived: t('participants.statusLabels.archived'),
  };

  const assignmentStatusLabels: Record<string, string> = {
    assigned: t('participants.assignmentAssigned'),
    in_progress: t('participants.assignmentInProgress'),
    completed: t('participants.assignmentCompleted'),
    closed: t('participants.assignmentClosed'),
  };

  useEffect(() => {
    fetchProjectParticipants(projectId)
      .then((rows) => {
        setParticipants(rows);
        setMessage(rows.length ? '' : t('participants.noParticipantsYet'));
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);
  useEffect(() => {
    if (!scheduleOpen || !projectId) return;
    void fetchProjectSchedule(projectId).then(setSchedule).catch((error: Error) => setMessage(error.message));
  }, [projectId, scheduleOpen]);
  useEffect(() => {
    if (!hasAnyCurrentProjectPermission(['identity.users.manage'])) return;
    void Promise.all([fetchTerritories(projectId), fetchCaseAssignees(projectId)]).then(([items, users]) => { setTerritories(items); setAssignees(users); }).catch(() => {});
  }, [projectId]);

  const filtered = participants.filter((participant) => {
    if (groupFilter && participant.group_name !== groupFilter) return false;
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return [participant.full_name, participant.document_id, participant.external_code, participant.department, participant.municipality]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle));
  });
  const groups = Array.from(new Set(participants.map((participant) => participant.group_name).filter((name): name is string => Boolean(name)))).sort();

  async function saveGroup(participantId: string) {
    try {
      const updated = await assignParticipantGroup(participantId, groupDraft);
      setParticipants((rows) => rows.map((row) => row.id === participantId ? updated : row));
      setEditingGroupId('');
      setMessage(t('participants.groupAssigned'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('participants.groupAssignError')); }
  }

  async function removeGroup() {
    if (!groupFilter || !window.confirm(t('participants.confirmRemoveGroup', { group: groupFilter, count: filtered.length }))) return;
    try {
      const count = await deleteParticipantGroup(projectId, groupFilter);
      setParticipants(await fetchProjectParticipants(projectId));
      setGroupFilter('');
      setMessage(t('participants.groupRemovedCount', { count }));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('participants.groupRemoveError')); }
  }

  async function changeGroupStatus(status: 'active' | 'inactive') {
    const statusLabel = status === 'active' ? t('participants.statusActive') : t('participants.statusInactive');
    if (!groupFilter || !window.confirm(t('participants.confirmChangeStatus', { status: statusLabel, group: groupFilter }))) return;
    try {
      const count = await setParticipantGroupStatus(projectId, groupFilter, status);
      setParticipants(await fetchProjectParticipants(projectId));
      setMessage(t('participants.statusUpdatedCount', { count }));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('participants.statusChangeError')); }
  }

  return (
    <AppShell title={t('participants.title')}>
      <main className="participants-shell">
        <header className="participants-header">
          <div>
            <h2>{t('participants.title')}</h2>
            <p>{t('participants.description')}</p>
          </div>
          <input type="search" placeholder={t('participants.searchPlaceholder')} value={query} onChange={(event) => setQuery(event.target.value)} />
        </header>
        <div className="participants-group-toolbar"><label>{t('participants.groupLabel')}<select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}><option value="">{t('participants.allGroups')}</option>{groups.map((group) => <option key={group} value={group}>{group}</option>)}</select></label><a href="/admin/excel-import">{t('participants.importExcel')}</a><span>{t('participants.participantCount', { count: filtered.length })}</span>{groupFilter && hasAnyCurrentProjectPermission(['identity.users.manage']) && <><button type="button" onClick={() => void changeGroupStatus('active')}>{t('participants.activateGroup')}</button><button type="button" onClick={() => void changeGroupStatus('inactive')}>{t('participants.deactivateGroup')}</button><button type="button" className="participants-remove-group" onClick={() => void removeGroup()}>{t('participants.deleteGroup')}</button></>}</div>
        {hasAnyCurrentProjectPermission(['identity.users.manage']) && <details className="participant-summary-card"><summary>{t('participants.territorialAccess')}</summary><p>{t('participants.territorialAccessDesc')}</p><div className="participants-group-toolbar"><select aria-label={t('participants.userLabel')} value={territoryUser} onChange={(event) => setTerritoryUser(event.target.value)}><option value="">{t('participants.selectUser')}</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select><input aria-label={t('participants.departmentLabel')} placeholder={t('participants.departmentPlaceholder')} value={department} onChange={(event) => setDepartment(event.target.value)} /><input aria-label={t('participants.municipalityLabel')} placeholder={t('participants.municipalityPlaceholder')} value={municipality} onChange={(event) => setMunicipality(event.target.value)} /><button type="button" onClick={() => { void assignTerritory(projectId, { user_id: territoryUser, department, municipality }).then(async () => { setTerritories(await fetchTerritories(projectId)); setDepartment(''); setMunicipality(''); setMessage(t('participants.territoryAssigned')); }).catch((error: Error) => setMessage(error.message)); }}>{t('participants.assignTerritory')}</button></div>{territories.map((item) => <p key={item.id}>{assignees.find((user) => user.id === item.user_id)?.full_name || item.user_id}: {item.department}{item.municipality ? ` / ${item.municipality}` : ''} <button type="button" onClick={() => { void removeTerritory(projectId, item.id).then(async () => setTerritories(await fetchTerritories(projectId))).catch((error: Error) => setMessage(error.message)); }}>{t('participants.removeTerritory')}</button></p>)}</details>}
        <section className="participant-summary-card"><button type="button" onClick={() => setScheduleOpen((current) => !current)}>{t('participants.internalSchedule')}</button>{scheduleOpen && <><p>{t('participants.internalScheduleHint')}</p><div className="records-table-wrap"><table className="records-table"><thead><tr><th>{t('participants.caseDueLabel')}</th><th>{t('participants.name')}</th><th>{t('participants.caseNameLabel')}</th><th>{t('participants.detail')}</th></tr></thead><tbody>{schedule.map((item) => <tr key={item.id}><td>{item.due_at ? new Date(item.due_at).toLocaleString() : '—'}</td><td>{item.participant_name}</td><td>{item.title}</td><td><a href={`/participants/${item.participant_id}`}>{t('participants.viewHistory')}</a></td></tr>)}</tbody></table></div></>}</section>
        {message ? <p role="status">{message}</p> : null}
        <div className="records-table-wrap">
          <table className="records-table">
            <thead>
              <tr>
                <th>{t('participants.name')}</th>
                <th>{t('participants.document')}</th>
                <th>{t('participants.externalCode')}</th>
                <th>{t('participants.type')}</th>
                <th>{t('participants.department')}</th>
                <th>{t('participants.municipality')}</th>
                <th>{t('participants.group')}</th>
                <th>{t('participants.status')}</th>
                <th>{t('participants.detail')}</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((participant) => (
                <tr key={participant.id}>
                  <td>{participant.full_name}</td>
                  <td>{participant.document_id || '—'}</td>
                  <td>{participant.external_code || '—'}</td>
                  <td>{participant.participant_type}</td>
                  <td>{participant.department || '—'}</td>
                  <td>{participant.municipality || '—'}</td>
                  <td>{editingGroupId === participant.id ? <span className="participants-group-edit"><input aria-label={t('participants.groupOfParticipant', { name: participant.full_name })} list="participant-group-options" value={groupDraft} maxLength={160} onChange={(event) => setGroupDraft(event.target.value)} /><button type="button" onClick={() => void saveGroup(participant.id)}>{t('app.save')}</button><button type="button" onClick={() => setEditingGroupId('')}>{t('app.cancel')}</button></span> : <span>{participant.group_name || t('participants.noGroup')} {hasAnyCurrentProjectPermission(['identity.users.manage']) && <button type="button" className="participants-group-action" onClick={() => { setEditingGroupId(participant.id); setGroupDraft(participant.group_name || ''); }}>{t('participants.assignGroup')}</button>}</span>}</td>
                  <td>{participant.status}</td>
                  <td><a href={`/participants/${participant.id}`}>{t('participants.viewHistory')}</a></td>
                </tr>
              ))}
            </tbody>
          </table>
          <datalist id="participant-group-options">{groups.map((group) => <option key={group} value={group} />)}</datalist>
        </div>
      </main>
    </AppShell>
  );
}

function ParticipantDetail({ participantId }: { participantId: string }) {
  const { t } = useI18n();
  const [participant, setParticipant] = useState<Participant | null>(null);
  const [history, setHistory] = useState<ParticipantHistoryItem[]>([]);
  const [activities, setActivities] = useState<ParticipantActivity[]>([]);
  const [message, setMessage] = useState(t('participants.loadingParticipant'));
  const [cases, setCases] = useState<ParticipantCase[]>([]);
  const [assignees, setAssignees] = useState<CaseAssignee[]>([]);
  const [caseTitle, setCaseTitle] = useState('');
  const [caseAssignee, setCaseAssignee] = useState('');
  const [caseDue, setCaseDue] = useState('');
  const [reminderEmail, setReminderEmail] = useState(false);
  const [reminderWhatsApp, setReminderWhatsApp] = useState(false);
  const [openEvents, setOpenEvents] = useState('');
  const [events, setEvents] = useState<CaseEvent[]>([]);

  const statusLabels: Record<string, string> = {
    draft: t('participants.statusLabels.draft'), submitted: t('participants.statusLabels.submitted'), under_review: t('participants.statusLabels.under_review'),
    tech_approved: t('participants.statusLabels.tech_approved'), coordinator_approved: t('participants.statusLabels.coordinator_approved'),
    returned: t('participants.statusLabels.returned'), corrected: t('participants.statusLabels.corrected'), approved: t('participants.statusLabels.approved'),
    rejected: t('participants.statusLabels.rejected'), cancelled: t('participants.statusLabels.cancelled'), archived: t('participants.statusLabels.archived'),
  };

  const assignmentStatusLabels: Record<string, string> = {
    assigned: t('participants.assignmentAssigned'),
    in_progress: t('participants.assignmentInProgress'),
    completed: t('participants.assignmentCompleted'),
    closed: t('participants.assignmentClosed'),
  };

  useEffect(() => {
    Promise.all([fetchParticipant(participantId), fetchParticipantHistory(participantId), fetchParticipantActivities(participantId), fetchParticipantCases(participantId)])
      .then(([participantData, historyData, activityData, caseData]) => {
        setParticipant(participantData);
        setHistory(historyData);
        setActivities(activityData);
        setCases(caseData);
        void fetchCaseAssignees(participantData.project_id).then(setAssignees).catch(() => {});
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [participantId]);

  if (message && !participant) {
    return (
      <AppShell title={t('participants.participant')}>
        <main className="participants-shell">
          <a href="/participants">{t('participants.backToParticipants')}</a>
          <p role="status">{message}</p>
        </main>
      </AppShell>
    );
  }
  if (!participant) return null;

  async function saveCase() {
    try {
      await createParticipantCase({ participant_id: participantId, title: caseTitle, assigned_user_id: caseAssignee || null, due_at: caseDue ? new Date(caseDue).toISOString().replace('Z', '') : null, reminder_channels: ['internal', ...(reminderEmail ? ['email'] : []), ...(reminderWhatsApp ? ['whatsapp'] : [])] });
      setCases(await fetchParticipantCases(participantId)); setCaseTitle(''); setCaseDue(''); setMessage(t('participants.caseCreated'));
    } catch (error) { setMessage(error instanceof Error ? error.message : t('participants.caseCreateError')); }
  }

  async function changeCase(id: string, data: { status?: string; assigned_user_id?: string | null; note?: string }) {
    try { await updateParticipantCase(id, data); setCases(await fetchParticipantCases(participantId)); setMessage(t('participants.caseUpdated')); }
    catch (error) { setMessage(error instanceof Error ? error.message : t('participants.caseUpdateError')); }
  }

  return (
    <AppShell title={t('participants.participant')}>
      <main className="participants-shell">
        <a href="/participants">{t('participants.backToParticipants')}</a>
        {message && <p role="status">{message}</p>}
        <section className="participant-summary-card">
          <h2>{participant.full_name}</h2>
          <dl className="record-detail">
            <div><dt>{t('participants.document')}</dt><dd>{participant.document_id || '—'}</dd></div>
            <div><dt>{t('participants.externalCode')}</dt><dd>{participant.external_code || '—'}</dd></div>
            <div><dt>{t('participants.type')}</dt><dd>{participant.participant_type}</dd></div>
            <div><dt>{t('participants.department')}</dt><dd>{participant.department || '—'}</dd></div>
            <div><dt>{t('participants.municipality')}</dt><dd>{participant.municipality || '—'}</dd></div>
            <div><dt>{t('participants.group')}</dt><dd>{participant.group_name || t('participants.noGroup')}</dd></div>
            <div><dt>{t('participants.status')}</dt><dd>{participant.status}</dd></div>
          </dl>
        </section>
        <section className="participant-summary-card"><h3>{t('participants.formTree')}</h3><p>{t('participants.formTreeDesc')}</p><div className="participant-activity-tree" role="tree" aria-label={t('participants.activityTreeLabel')}>{activities.map((activity) => <div key={activity.template_id} className="participant-activity-node" role="treeitem"><div><strong>{'▸'} {activity.template_name}</strong><span className={`record-status ${activity.assignment_status}`}>{assignmentStatusLabels[activity.assignment_status] || activity.assignment_status}</span></div><small>{t('participants.responsible')}: {activity.responsible_name || t('participants.responsibleHistorical')}{activity.record_status ? ` · ${t('participants.responseLabel')}: ${statusLabels[activity.record_status] || activity.record_status}` : ''}</small><div>{activity.record_id ? <a href={`/records/${activity.template_id}?recordId=${activity.record_id}${activity.record_status === 'returned' && hasAnyCurrentProjectPermission(['records.write']) ? '&edit=1' : ''}`}>{activity.record_status === 'returned' ? t('participants.correctResponse') : t('participants.viewResponse')}</a> : activity.assignment_status === 'assigned' || activity.assignment_status === 'in_progress' ? <a href={`/runtime/${activity.template_id}?participantId=${participantId}`}>{t('participants.fillIn')}</a> : null}</div></div>)}{!activities.length && <p>{t('participants.noFormsForParticipant')}</p>}</div></section>
        {hasAnyCurrentProjectPermission(['records.write']) && <div className="participants-group-toolbar" aria-label={t('participants.deadlineNotice')}><strong>{t('participants.deadlineNotice')}</strong><label><input type="checkbox" checked readOnly /> {t('participants.internalNotice')}</label><label><input type="checkbox" checked={reminderEmail} onChange={(event) => setReminderEmail(event.target.checked)} /> {t('participants.emailNotice')}</label><label><input type="checkbox" checked={reminderWhatsApp} onChange={(event) => setReminderWhatsApp(event.target.checked)} /> {t('participants.whatsappNotice')}</label></div>}
        <section className="participant-summary-card"><h3>{t('participants.casesAndReferrals', { count: cases.length })}</h3><p>{t('participants.casesDesc')}</p>{hasAnyCurrentProjectPermission(['records.write']) && <div className="participants-group-toolbar"><input aria-label={t('participants.caseNameLabel')} placeholder={t('participants.caseNamePlaceholder')} value={caseTitle} onChange={(event) => setCaseTitle(event.target.value)} /><select aria-label={t('participants.responsibleLabel')} value={caseAssignee} onChange={(event) => setCaseAssignee(event.target.value)}><option value="">{t('participants.noResponsible')}</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select><input aria-label={t('participants.caseDueLabel')} type="datetime-local" value={caseDue} onChange={(event) => setCaseDue(event.target.value)} /><button type="button" disabled={caseTitle.trim().length < 3} onClick={() => void saveCase()}>{t('participants.createCase')}</button></div>}{cases.map((item) => <article key={item.id} className="participant-summary-card"><strong>{item.title}</strong> {'·'} {item.status} {'·'} {t('participants.responsible')}: {assignees.find((user) => user.id === item.assigned_user_id)?.full_name || t('participants.noAssigned')} {'·'} {t('participants.deadline')}: {item.due_at ? new Date(`${item.due_at}Z`).toLocaleString() : t('participants.noDeadline')}<div className="participants-group-toolbar">{hasAnyCurrentProjectPermission(['records.write']) && <><select aria-label={t('participants.caseStatusLabel', { title: item.title })} value={item.status} onChange={(event) => void changeCase(item.id, { status: event.target.value })}><option value="open">{t('participants.caseStatusOpen')}</option><option value="in_progress">{t('participants.caseStatusInProgress')}</option><option value="referred">{t('participants.caseStatusReferred')}</option><option value="closed">{t('participants.caseStatusClosed')}</option></select><select aria-label={t('participants.caseReferLabel', { title: item.title })} value={item.assigned_user_id || ''} onChange={(event) => void changeCase(item.id, { assigned_user_id: event.target.value || null })}><option value="">{t('participants.noResponsible')}</option>{assignees.map((user) => <option key={user.id} value={user.id}>{user.full_name}</option>)}</select></>}<button type="button" onClick={() => { if (openEvents === item.id) { setOpenEvents(''); return; } void fetchCaseEvents(item.id).then(setEvents); setOpenEvents(item.id); }}>{t('participants.caseHistory')}</button></div>{openEvents === item.id && <ul>{events.map((event) => <li key={event.id}>{new Date(event.created_at).toLocaleString()} {'·'} {event.event_type} {event.note || ''}</li>)}</ul>}</article>)}</section>
        <section>
          <h3>{t('participants.unifiedHistory', { count: history.length })}</h3>
          {history.length ? (
            <div className="records-table-wrap">
              <table className="records-table">
                <thead>
                  <tr>
                    <th>{t('participants.form')}</th>
                    <th>{t('participants.status')}</th>
                    <th>{t('participants.date')}</th>
                    <th>{t('participants.capturedBy')}</th>
                    <th>{t('participants.detail')}</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item) => (
                    <tr key={item.record_id}>
                      <td>{item.template_name}</td>
                      <td><span className={`record-status ${item.status}`}>{statusLabels[item.status] ?? item.status}</span></td>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td>{item.submitted_by || '—'}</td>
                      <td><a href={`/records/${item.template_id}?recordId=${item.record_id}`}>{t('participants.viewRecord')}</a></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>{t('participants.noFormsLinked')}</p>
          )}
        </section>
      </main>
    </AppShell>
  );
}
