import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchMyFormAssignments, type MyFormAssignment } from './myFormsApi';

export function MyFormsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [assignments, setAssignments] = useState<MyFormAssignment[]>([]);
  const [message, setMessage] = useState('Cargando tus formularios...');

  useEffect(() => {
    if (!projectId) { setMessage('Selecciona un proyecto para ver tus formularios.'); return; }
    fetchMyFormAssignments(projectId)
      .then((rows) => { setAssignments(rows); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const forms = Array.from(new Set(assignments.map((item) => item.template_id)));
  return <AppShell title="Mis formularios"><main className="forms-home">
    <header className="forms-home-head"><div><h1>Mis formularios asignados</h1><p>Participantes que puedes atender en este proyecto.</p></div></header>
    {message && <p role="status">{message}</p>}
    {!message && !assignments.length && <p>No tienes formularios publicados con participantes asignados. Pide al administrador que te asigne participantes en la configuración del formulario.</p>}
    {forms.map((templateId) => {
      const rows = assignments.filter((item) => item.template_id === templateId);
      return <section className="forms-detail-panel" key={templateId}>
        <h2>{rows[0].template_name}</h2><p>{rows.length} participante(s) asignado(s)</p>
        <div className="records-table-wrap"><table className="records-table"><thead><tr><th>Participante</th><th>Documento</th><th>Estado</th><th>Acción</th></tr></thead><tbody>
          {rows.map((item) => <tr key={item.participant_id}><td>{item.participant_name}</td><td>{item.document_id || '—'}</td><td>{item.assignment_status === 'assigned' ? 'Asignado' : item.assignment_status === 'in_progress' ? 'En curso' : item.assignment_status === 'completed' ? 'Completado' : item.assignment_status === 'closed' ? 'Cerrado' : item.assignment_status}</td><td>{item.record_id ? <a href={`/records/${item.template_id}?recordId=${item.record_id}`}>Ver respuesta</a> : ['assigned', 'in_progress'].includes(item.assignment_status) ? <a href={`/runtime/${item.template_id}?participantId=${item.participant_id}`}>Diligenciar</a> : '—'}</td></tr>)}
        </tbody></table></div>
      </section>;
    })}
  </main></AppShell>;
}
