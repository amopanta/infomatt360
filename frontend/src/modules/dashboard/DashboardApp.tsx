import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { hasAnyCurrentProjectPermission, PROJECT_KEY } from '../auth/session';
import { fetchMyFormSummary, type MyFormSummary } from '../builder/myFormsApi';
import { fetchDashboard } from './api';
import type { DashboardSummary } from './api';

export function DashboardApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [myAssignments, setMyAssignments] = useState<MyFormSummary | null>(null);
  const [message, setMessage] = useState('Cargando resumen del proyecto...');
  useEffect(() => { fetchDashboard(projectId).then((result) => { setSummary(result); setMessage(''); }).catch((error: Error) => setMessage(error.message)); }, [projectId]);
  useEffect(() => { if (projectId && hasAnyCurrentProjectPermission(['records.write'])) void fetchMyFormSummary(projectId).then(setMyAssignments).catch(() => setMyAssignments(null)); }, [projectId]);
  const formCount = myAssignments?.form_count ?? 0;
  return <AppShell title="Dashboard"><main className="dashboard-shell">{message ? <p role="status">{message}</p> : null}{summary ? <><section className="dashboard-cards"><MetricCard label="Mis formularios" value={formCount} detail={`${(myAssignments?.assignment_count ?? 0)} participante(s) asignado(s)`} href="/my-forms" /><MetricCard label="Registros" value={summary.records_total} detail={statusSummary(summary.records_by_status)} href="/records" /><MetricCard label="Usuarios activos" value={summary.users_total} detail="Asignados al proyecto" href="/admin/users" /><MetricCard label="Evidencias" value={summary.files_total} detail={formatBytes(summary.storage_bytes)} href="/records" /></section>{(myAssignments?.assignment_count ?? 0) > 0 && <section className="dashboard-panel"><header><div><h2>Mis formularios asignados</h2><p>Abre la captura del participante que te corresponde.</p></div><a href="/my-forms">Ver todos</a></header><div className="dashboard-activity">{(myAssignments?.pending ?? []).map((item) => <a key={`${item.template_id}:${item.participant_id}`} href={`/runtime/${item.template_id}?participantId=${item.participant_id}`}><span><strong>{item.template_name}</strong><small>{item.participant_name} · {item.document_id || 'Sin documento'}</small></span><span>Diligenciar</span></a>)}</div></section>}<section className="dashboard-panel"><header><div><h2>Actividad reciente</h2><p>Últimos registros recibidos en el proyecto.</p></div><a href="/records">Ver todos</a></header>{summary.recent_records.length ? <div className="dashboard-activity">{summary.recent_records.map((record) => <a key={record.id} href={`/records/${record.template_id}`}><span><strong>{record.template_name}</strong><small>{new Date(record.created_at).toLocaleString()}</small></span><em className={`record-status ${record.status}`}>{record.status}</em></a>)}</div> : <p>Todavía no hay actividad registrada.</p>}</section></> : null}</main></AppShell>;
}

function MetricCard({ label, value, detail, href }: { label: string; value: number; detail: string; href: string }) {
  return <a className="dashboard-metric" href={href}><span>{label}</span><strong>{value.toLocaleString()}</strong><small>{detail}</small></a>;
}

function statusSummary(values: Record<string, number>): string {
  const parts = Object.entries(values).map(([status, count]) => `${count} ${status}`);
  return parts.join(' · ') || 'Sin capturas';
}

function formatBytes(value: number): string {
  if (value < 1024) return `${value} B almacenados`;
  if (value < 1024 ** 2) return `${(value / 1024).toFixed(1)} KB almacenados`;
  return `${(value / 1024 ** 2).toFixed(1)} MB almacenados`;
}
