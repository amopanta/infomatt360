import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { assignParticipantGroup, assignTerritory, createParticipantCase, deleteParticipantGroup, fetchCaseAssignees, fetchCaseEvents, fetchParticipant, fetchParticipantActivities, fetchParticipantCases, fetchParticipantHistory, fetchProjectParticipants, fetchTerritories, removeTerritory, setParticipantGroupStatus, updateParticipantCase } from './api';
import type { CaseAssignee, CaseEvent, Participant, ParticipantActivity, ParticipantCase, ParticipantHistoryItem, UserTerritory } from './api';

const STATUS_LABELS: Record<string, string> = {
  draft: 'Borrador', submitted: 'Enviado', under_review: 'En revisión',
  tech_approved: 'Aprobado técnico', coordinator_approved: 'Aprobado coordinación',
  returned: 'Devuelto', corrected: 'Corregido', approved: 'Aprobado',
  rejected: 'Rechazado', cancelled: 'Cancelado', archived: 'Archivado',
};

function participantIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[0] === 'participants' ? parts[1] ?? '' : '';
}

export function ParticipantsApp() {
  const participantId = participantIdFromPath();
  return participantId ? <ParticipantDetail participantId={participantId} /> : <ParticipantList />;
}

function ParticipantList() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [query, setQuery] = useState('');
  const [groupFilter, setGroupFilter] = useState('');
  const [editingGroupId, setEditingGroupId] = useState('');
  const [groupDraft, setGroupDraft] = useState('');
  const [message, setMessage] = useState('Cargando participantes...');
  const [territories, setTerritories] = useState<UserTerritory[]>([]);
  const [assignees, setAssignees] = useState<CaseAssignee[]>([]);
  const [territoryUser, setTerritoryUser] = useState('');
  const [department, setDepartment] = useState('');
  const [municipality, setMunicipality] = useState('');

  useEffect(() => {
    fetchProjectParticipants(projectId)
      .then((rows) => {
        setParticipants(rows);
        setMessage(rows.length ? '' : 'Este proyecto aún no tiene participantes registrados.');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);
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
      setMessage('Grupo asignado.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible asignar el grupo.'); }
  }

  async function removeGroup() {
    if (!groupFilter || !window.confirm(`¿Quitar el grupo «${groupFilter}» de ${filtered.length} participante(s)? Sus datos y respuestas se conservarán.`)) return;
    try {
      const count = await deleteParticipantGroup(projectId, groupFilter);
      setParticipants(await fetchProjectParticipants(projectId));
      setGroupFilter('');
      setMessage(`Grupo quitado de ${count} participante(s).`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible eliminar el grupo.'); }
  }

  async function changeGroupStatus(status: 'active' | 'inactive') {
    if (!groupFilter || !window.confirm(`¿Cambiar a ${status === 'active' ? 'activo' : 'inactivo'} el estado de todos los participantes del grupo «${groupFilter}»?`)) return;
    try {
      const count = await setParticipantGroupStatus(projectId, groupFilter, status);
      setParticipants(await fetchProjectParticipants(projectId));
      setMessage(`Estado actualizado para ${count} participante(s).`);
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible cambiar el estado.'); }
  }

  return (
    <AppShell title="Participantes">
      <main className="participants-shell">
        <header className="participants-header">
          <div>
            <h2>Participantes</h2>
            <p>Eje central del sistema: cada participante agrupa todos los formularios capturados sobre él, sin importar el canal (web, móvil, carga masiva, API).</p>
          </div>
          <input type="search" placeholder="Buscar por nombre, documento, código o municipio" value={query} onChange={(event) => setQuery(event.target.value)} />
        </header>
        <div className="participants-group-toolbar"><label>Grupo de participantes<select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}><option value="">Todos los grupos</option>{groups.map((group) => <option key={group} value={group}>{group}</option>)}</select></label><a href="/admin/excel-import">Importar o actualizar desde Excel</a><span>{filtered.length} participante(s)</span>{groupFilter && hasAnyCurrentProjectPermission(['identity.users.manage']) && <><button type="button" onClick={() => void changeGroupStatus('active')}>Activar grupo</button><button type="button" onClick={() => void changeGroupStatus('inactive')}>Desactivar grupo</button><button type="button" className="participants-remove-group" onClick={() => void removeGroup()}>Eliminar grupo</button></>}</div>
        {hasAnyCurrentProjectPermission(['identity.users.manage']) && <details className="participant-summary-card"><summary>Acceso territorial</summary><p>Asigna departamentos o municipios. Un usuario con territorios asignados verá únicamente los participantes de esas zonas.</p><div className="participants-group-toolbar"><select aria-label="Usuario" value={territoryUser} onChange={(event) => setTerritoryUser(event.target.value)}><option value="">Seleccionar usuario</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select><input aria-label="Departamento" placeholder="Departamento" value={department} onChange={(event) => setDepartment(event.target.value)} /><input aria-label="Municipio opcional" placeholder="Municipio (opcional)" value={municipality} onChange={(event) => setMunicipality(event.target.value)} /><button type="button" onClick={() => { void assignTerritory(projectId, { user_id: territoryUser, department, municipality }).then(async () => { setTerritories(await fetchTerritories(projectId)); setDepartment(''); setMunicipality(''); setMessage('Territorio asignado.'); }).catch((error: Error) => setMessage(error.message)); }}>Asignar</button></div>{territories.map((item) => <p key={item.id}>{assignees.find((user) => user.id === item.user_id)?.full_name || item.user_id}: {item.department}{item.municipality ? ` / ${item.municipality}` : ''} <button type="button" onClick={() => { void removeTerritory(projectId, item.id).then(async () => setTerritories(await fetchTerritories(projectId))).catch((error: Error) => setMessage(error.message)); }}>Quitar</button></p>)}</details>}
        {message ? <p role="status">{message}</p> : null}
        <div className="records-table-wrap">
          <table className="records-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Documento</th>
                <th>Código externo</th>
                <th>Tipo</th>
                <th>Departamento</th>
                <th>Municipio</th>
                <th>Grupo</th>
                <th>Estado</th>
                <th>Detalle</th>
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
                  <td>{editingGroupId === participant.id ? <span className="participants-group-edit"><input aria-label={`Grupo de ${participant.full_name}`} list="participant-group-options" value={groupDraft} maxLength={160} onChange={(event) => setGroupDraft(event.target.value)} /><button type="button" onClick={() => void saveGroup(participant.id)}>Guardar</button><button type="button" onClick={() => setEditingGroupId('')}>Cancelar</button></span> : <span>{participant.group_name || 'Sin grupo'} {hasAnyCurrentProjectPermission(['identity.users.manage']) && <button type="button" className="participants-group-action" onClick={() => { setEditingGroupId(participant.id); setGroupDraft(participant.group_name || ''); }}>Asignar</button>}</span>}</td>
                  <td>{participant.status}</td>
                  <td><a href={`/participants/${participant.id}`}>Ver historial</a></td>
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
  const [participant, setParticipant] = useState<Participant | null>(null);
  const [history, setHistory] = useState<ParticipantHistoryItem[]>([]);
  const [activities, setActivities] = useState<ParticipantActivity[]>([]);
  const [message, setMessage] = useState('Cargando participante...');
  const [cases, setCases] = useState<ParticipantCase[]>([]);
  const [assignees, setAssignees] = useState<CaseAssignee[]>([]);
  const [caseTitle, setCaseTitle] = useState('');
  const [caseAssignee, setCaseAssignee] = useState('');
  const [caseDue, setCaseDue] = useState('');
  const [reminderEmail, setReminderEmail] = useState(false);
  const [reminderWhatsApp, setReminderWhatsApp] = useState(false);
  const [openEvents, setOpenEvents] = useState('');
  const [events, setEvents] = useState<CaseEvent[]>([]);

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
      <AppShell title="Participante">
        <main className="participants-shell">
          <a href="/participants">Volver a participantes</a>
          <p role="status">{message}</p>
        </main>
      </AppShell>
    );
  }
  if (!participant) return null;

  async function saveCase() {
    try {
      await createParticipantCase({ participant_id: participantId, title: caseTitle, assigned_user_id: caseAssignee || null, due_at: caseDue ? new Date(caseDue).toISOString().replace('Z', '') : null, reminder_channels: ['internal', ...(reminderEmail ? ['email'] : []), ...(reminderWhatsApp ? ['whatsapp'] : [])] });
      setCases(await fetchParticipantCases(participantId)); setCaseTitle(''); setCaseDue(''); setMessage('Caso creado.');
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible crear el caso.'); }
  }

  async function changeCase(id: string, data: { status?: string; assigned_user_id?: string | null; note?: string }) {
    try { await updateParticipantCase(id, data); setCases(await fetchParticipantCases(participantId)); setMessage('Caso actualizado.'); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el caso.'); }
  }

  return (
    <AppShell title="Participante">
      <main className="participants-shell">
        <a href="/participants">Volver a participantes</a>
        {message && <p role="status">{message}</p>}
        <section className="participant-summary-card">
          <h2>{participant.full_name}</h2>
          <dl className="record-detail">
            <div><dt>Documento</dt><dd>{participant.document_id || '—'}</dd></div>
            <div><dt>Código externo</dt><dd>{participant.external_code || '—'}</dd></div>
            <div><dt>Tipo</dt><dd>{participant.participant_type}</dd></div>
            <div><dt>Departamento</dt><dd>{participant.department || '—'}</dd></div>
            <div><dt>Municipio</dt><dd>{participant.municipality || '—'}</dd></div>
            <div><dt>Grupo</dt><dd>{participant.group_name || 'Sin grupo'}</dd></div>
            <div><dt>Estado</dt><dd>{participant.status}</dd></div>
          </dl>
        </section>
        <section className="participant-summary-card"><h3>Árbol de formularios y actividades</h3><p>Solo aparecen las actividades que corresponden a este participante y a tu acceso.</p><div className="participant-activity-tree" role="tree" aria-label="Actividades del participante">{activities.map((activity) => <div key={activity.template_id} className="participant-activity-node" role="treeitem"><div><strong>▸ {activity.template_name}</strong><span className={`record-status ${activity.assignment_status}`}>{({ assigned: 'Asignado', in_progress: 'En curso', completed: 'Completado', closed: 'Cerrado' } as const)[activity.assignment_status] || activity.assignment_status}</span></div><small>Responsable: {activity.responsible_name || 'Histórico'}{activity.record_status ? ` · Respuesta: ${STATUS_LABELS[activity.record_status] || activity.record_status}` : ''}</small><div>{activity.record_id ? <a href={`/records/${activity.template_id}?recordId=${activity.record_id}${activity.record_status === 'returned' && hasAnyCurrentProjectPermission(['records.write']) ? '&edit=1' : ''}`}>{activity.record_status === 'returned' ? 'Corregir respuesta' : 'Ver respuesta'}</a> : activity.assignment_status === 'assigned' || activity.assignment_status === 'in_progress' ? <a href={`/runtime/${activity.template_id}?participantId=${participantId}`}>Diligenciar</a> : null}</div></div>)}{!activities.length && <p>No hay formularios asignados o realizados visibles para este participante.</p>}</div></section>
        {hasAnyCurrentProjectPermission(['records.write']) && <div className="participants-group-toolbar" aria-label="Canales de aviso del nuevo caso"><strong>Al llegar el plazo:</strong><label><input type="checkbox" checked readOnly /> Aviso interno</label><label><input type="checkbox" checked={reminderEmail} onChange={(event) => setReminderEmail(event.target.checked)} /> Correo</label><label><input type="checkbox" checked={reminderWhatsApp} onChange={(event) => setReminderWhatsApp(event.target.checked)} /> WhatsApp</label></div>}
        <section className="participant-summary-card"><h3>Casos y remisiones ({cases.length})</h3><p>Da seguimiento al participante, asigna un responsable y fija un plazo. El responsable recibirá un aviso interno al llegar la fecha.</p>{hasAnyCurrentProjectPermission(['records.write']) && <div className="participants-group-toolbar"><input aria-label="Nombre del caso" placeholder="Nombre del caso" value={caseTitle} onChange={(event) => setCaseTitle(event.target.value)} /><select aria-label="Responsable" value={caseAssignee} onChange={(event) => setCaseAssignee(event.target.value)}><option value="">Sin responsable</option>{assignees.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}</select><input aria-label="Plazo del caso" type="datetime-local" value={caseDue} onChange={(event) => setCaseDue(event.target.value)} /><button type="button" disabled={caseTitle.trim().length < 3} onClick={() => void saveCase()}>Crear caso</button></div>}{cases.map((item) => <article key={item.id} className="participant-summary-card"><strong>{item.title}</strong> · {item.status} · Responsable: {assignees.find((user) => user.id === item.assigned_user_id)?.full_name || 'Sin asignar'} · Plazo: {item.due_at ? new Date(`${item.due_at}Z`).toLocaleString() : 'Sin plazo'}<div className="participants-group-toolbar">{hasAnyCurrentProjectPermission(['records.write']) && <><select aria-label={`Estado de ${item.title}`} value={item.status} onChange={(event) => void changeCase(item.id, { status: event.target.value })}><option value="open">Abierto</option><option value="in_progress">En seguimiento</option><option value="referred">Remitido</option><option value="closed">Cerrado</option></select><select aria-label={`Remitir ${item.title}`} value={item.assigned_user_id || ''} onChange={(event) => void changeCase(item.id, { assigned_user_id: event.target.value || null })}><option value="">Sin responsable</option>{assignees.map((user) => <option key={user.id} value={user.id}>{user.full_name}</option>)}</select></>}<button type="button" onClick={() => { if (openEvents === item.id) { setOpenEvents(''); return; } void fetchCaseEvents(item.id).then(setEvents); setOpenEvents(item.id); }}>Historial</button></div>{openEvents === item.id && <ul>{events.map((event) => <li key={event.id}>{new Date(event.created_at).toLocaleString()} · {event.event_type} {event.note || ''}</li>)}</ul>}</article>)}</section>
        <section>
          <h3>Historial unificado ({history.length} formulario(s))</h3>
          {history.length ? (
            <div className="records-table-wrap">
              <table className="records-table">
                <thead>
                  <tr>
                    <th>Formulario</th>
                    <th>Estado</th>
                    <th>Fecha</th>
                    <th>Capturado por</th>
                    <th>Detalle</th>
                  </tr>
                </thead>
                <tbody>
                  {history.map((item) => (
                    <tr key={item.record_id}>
                      <td>{item.template_name}</td>
                      <td><span className={`record-status ${item.status}`}>{STATUS_LABELS[item.status] ?? item.status}</span></td>
                      <td>{new Date(item.created_at).toLocaleString()}</td>
                      <td>{item.submitted_by || '—'}</td>
                      <td><a href={`/records/${item.template_id}?recordId=${item.record_id}`}>Ver registro</a></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <p>Este participante aún no tiene formularios enlazados en ningún canal.</p>
          )}
        </section>
      </main>
    </AppShell>
  );
}
