import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchParticipant, fetchParticipantHistory, fetchProjectParticipants } from './api';
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
    const needle = query.trim().toLowerCase();
    if (!needle) return true;
    return [participant.full_name, participant.document_id, participant.external_code]
      .filter(Boolean)
      .some((value) => String(value).toLowerCase().includes(needle));
  });

  return (
    <AppShell title="Participantes">
      <main className="participants-shell">
        <header className="participants-header">
          <div>
            <h2>Participantes</h2>
            <p>Eje central del sistema: cada participante agrupa todos los formularios capturados sobre él, sin importar el canal (web, móvil, carga masiva, API).</p>
          </div>
          <input type="search" placeholder="Buscar por nombre, documento o código" value={query} onChange={(event) => setQuery(event.target.value)} />
        </header>
        {message ? <p role="status">{message}</p> : null}
        <div className="records-table-wrap">
          <table className="records-table">
            <thead>
              <tr>
                <th>Nombre</th>
                <th>Documento</th>
                <th>Código externo</th>
                <th>Tipo</th>
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
                  <td>{participant.status}</td>
                  <td><a href={`/participants/${participant.id}`}>Ver historial</a></td>
                </tr>
              ))}
            </tbody>
          </table>
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
