import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { assignParticipantGroup, fetchParticipant, fetchParticipantHistory, fetchProjectParticipants } from './api';
import type { Participant, ParticipantHistoryItem } from './api';

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

  useEffect(() => {
    fetchProjectParticipants(projectId)
      .then((rows) => {
        setParticipants(rows);
        setMessage(rows.length ? '' : 'Este proyecto aún no tiene participantes registrados.');
      })
      .catch((error: Error) => setMessage(error.message));
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
        <div className="participants-group-toolbar"><label>Grupo de participantes<select value={groupFilter} onChange={(event) => setGroupFilter(event.target.value)}><option value="">Todos los grupos</option>{groups.map((group) => <option key={group} value={group}>{group}</option>)}</select></label><a href="/admin/excel-import">Importar participantes desde Excel</a><span>{filtered.length} participante(s)</span></div>
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
  const [message, setMessage] = useState('Cargando participante...');

  useEffect(() => {
    Promise.all([fetchParticipant(participantId), fetchParticipantHistory(participantId)])
      .then(([participantData, historyData]) => {
        setParticipant(participantData);
        setHistory(historyData);
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [participantId]);

  if (message) {
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

  return (
    <AppShell title="Participante">
      <main className="participants-shell">
        <a href="/participants">Volver a participantes</a>
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
