import { Fragment, useEffect, useMemo, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { applyReviewAction, downloadTemplateRecords, fetchProjectTemplates, fetchRecord, fetchReviewActions, fetchReviewApprovalProgress, fetchReviewFlowComparison, fetchReviewNextActions, searchTemplateRecords } from './api';
import type { ReviewAction, ReviewApprovalProgress, ReviewFlowComparison, ReviewFlowSnapshot, ReviewNextAction, RuntimeRecord, TemplateSummary } from './api';

const REJECTION_STATUSES = new Set(['rejected', 'returned']);

const PAGE_SIZE = 25;

function templateIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[0] === 'records' ? parts[1] ?? '' : '';
}

const REVIEW_ACTIONS: Record<string, Array<{ label: string; toStatus: string; action: string }>> = {
  draft: [
    { label: 'Enviar', toStatus: 'submitted', action: 'submit' },
    { label: 'Cancelar', toStatus: 'cancelled', action: 'cancel' },
  ],
  submitted: [
    { label: 'Iniciar revisión', toStatus: 'under_review', action: 'start_review' },
    { label: 'Aprobar', toStatus: 'approved', action: 'approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
  ],
  under_review: [
    { label: 'Aprobación técnica', toStatus: 'tech_approved', action: 'technical_approve' },
    { label: 'Aprobar', toStatus: 'approved', action: 'approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
  ],
  tech_approved: [
    { label: 'Aprobación coordinador', toStatus: 'coordinator_approved', action: 'coordinator_approve' },
    { label: 'Aprobar final', toStatus: 'approved', action: 'approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
  ],
  coordinator_approved: [
    { label: 'Aprobar final', toStatus: 'approved', action: 'final_approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
  ],
  returned: [{ label: 'Marcar corregido', toStatus: 'corrected', action: 'mark_corrected' }],
  corrected: [{ label: 'Reenviar a revisión', toStatus: 'under_review', action: 'resubmit_review' }],
  approved: [{ label: 'Archivar', toStatus: 'archived', action: 'archive' }],
  rejected: [{ label: 'Archivar', toStatus: 'archived', action: 'archive' }],
};

function FlowSnapshotSummary({ title, snapshot }: { title: string; snapshot?: ReviewFlowSnapshot | null }) {
  if (!snapshot) return <article><strong>{title}</strong><span>Sin flujo configurado.</span></article>;
  return (
    <article>
      <strong>{title}</strong>
      <span>{snapshot.name || 'Flujo sin nombre'} · versión {snapshot.flow_version || '—'} · {snapshot.steps.length} paso(s)</span>
      <small>{snapshot.steps.map((step) => `${step.step_order}. ${step.action_label} → ${step.status_after}`).join(' · ') || 'Sin pasos activos'}</small>
    </article>
  );
}

function ReviewPanel({
  projectId,
  record,
  onMessage,
}: {
  projectId: string;
  record: RuntimeRecord;
  onMessage: (value: string) => void;
}) {
  const [history, setHistory] = useState<ReviewAction[]>([]);
  const [nextActions, setNextActions] = useState<ReviewNextAction[]>([]);
  const [approvalProgress, setApprovalProgress] = useState<ReviewApprovalProgress[]>([]);
  const [flowComparison, setFlowComparison] = useState<ReviewFlowComparison | null>(null);
  const [notes, setNotes] = useState('');
  const [rejectedFieldName, setRejectedFieldName] = useState('');
  const fallbackActions = REVIEW_ACTIONS[record.status] ?? [];
  const actions = nextActions.length
    ? nextActions.map((item) => ({ label: item.label, toStatus: item.to_status, action: item.action, source: item.source }))
    : fallbackActions;
  const showFieldSelector = actions.some((item) => REJECTION_STATUSES.has(item.toStatus));

  async function loadReviewState() {
    await Promise.all([
      fetchReviewActions(record.id).then(setHistory).catch(() => setHistory([])),
      fetchReviewNextActions(record.id).then(setNextActions).catch(() => setNextActions([])),
      fetchReviewApprovalProgress(record.id).then(setApprovalProgress).catch(() => setApprovalProgress([])),
      fetchReviewFlowComparison(record.id).then(setFlowComparison).catch(() => setFlowComparison(null)),
    ]);
  }

  useEffect(() => {
    void loadReviewState();
  }, [record.id, record.status]);

  async function submit(action: { label: string; toStatus: string; action: string }) {
    try {
      const fieldName = REJECTION_STATUSES.has(action.toStatus) ? rejectedFieldName : undefined;
      await applyReviewAction({ projectId, recordId: record.id, toStatus: action.toStatus, action: action.action, notes, rejectedFieldName: fieldName || undefined });
      await loadReviewState();
      onMessage(`Acción aplicada: ${action.label}.`);
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible aplicar la revisión.');
    }
  }

  return (
    <section className="review-panel">
      <h3>Flujo de revisión</h3>
      {flowComparison?.has_snapshot ? (
        <div className={`review-flow-comparison ${flowComparison.changed ? 'changed' : ''}`}>
          <header>
            <strong>Comparación del flujo</strong>
            <span>{flowComparison.changed ? 'El flujo actual cambió frente al snapshot del registro.' : 'El flujo actual coincide con el snapshot del registro.'}</span>
          </header>
          <div>
            <FlowSnapshotSummary title="Snapshot del registro" snapshot={flowComparison.snapshot} />
            <FlowSnapshotSummary title="Flujo actual" snapshot={flowComparison.current} />
          </div>
          {flowComparison.differences.length ? (
            <ul className="review-flow-differences">
              {flowComparison.differences.map((item) => <li key={item}>{item}</li>)}
            </ul>
          ) : null}
        </div>
      ) : null}
      {approvalProgress.length ? (
        <div className="review-progress">
          {approvalProgress.map((item) => (
            <article key={`${item.action}-${item.to_status}`}>
              <strong>Aprobación parcial: {item.label}</strong>
              <span>{item.approved_count} de {item.required_count} aprobadores completados · faltan {item.pending_count}</span>
              <small>Destino: {item.to_status}</small>
            </article>
          ))}
        </div>
      ) : null}
      <label>
        Observación
        <textarea rows={2} value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      {showFieldSelector ? (
        <label>
          Campo con error (para el enlace de corrección por WhatsApp)
          <select value={rejectedFieldName} onChange={(event) => setRejectedFieldName(event.target.value)}>
            <option value="">Sin campo específico</option>
            {record.values.map((value) => <option key={value.id} value={value.field_name}>{value.field_name}</option>)}
          </select>
        </label>
      ) : null}
      <div className="review-actions">
        {actions.length ? (
          actions.map((item) => <button key={item.action} onClick={() => void submit(item)}>{item.label}</button>)
        ) : (
          <span>Sin acciones disponibles para este estado.</span>
        )}
      </div>
      <div className="review-history">
        <strong>Historial</strong>
        {history.length ? (
          history.map((item) => (
            <p key={item.id}>
              {item.created_at ? new Date(item.created_at).toLocaleString() : ''} · {item.action}: {item.from_status || '—'} → {item.to_status}
              {item.approval_flow_version ? ` · flujo v${item.approval_flow_version}` : ''}
              {item.notes ? ` · ${item.notes}` : ''}
              {item.rejected_field_name ? ` · Campo: ${item.rejected_field_name}` : ''}
            </p>
          ))
        ) : (
          <p>Sin acciones registradas.</p>
        )}
      </div>
    </section>
  );
}

export function RecordsApp() {
  const templateId = templateIdFromPath();
  return templateId ? <RecordTable templateId={templateId} /> : <TemplateList />;
}

function TemplateList() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [message, setMessage] = useState('Cargando formularios...');

  useEffect(() => {
    fetchProjectTemplates(projectId)
      .then((rows) => {
        setTemplates(rows);
        setMessage(rows.length ? '' : 'Este proyecto aún no tiene formularios.');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  return (
    <AppShell title="Registros">
      <main className="records-shell">
        {message ? <p role="status">{message}</p> : null}
        <div className="record-template-grid">
          {templates.map((template) => (
            <a className="record-template-card" key={template.id} href={`/records/${template.id}`}>
              <strong>{template.name}</strong>
              <span>{template.description || 'Sin descripción'}</span>
              <small>{template.status}</small>
            </a>
          ))}
        </div>
      </main>
    </AppShell>
  );
}

function DeepLinkedRecordCard({
  projectId,
  record,
  highlightField,
  onMessage,
}: {
  projectId: string;
  record: RuntimeRecord;
  highlightField: string;
  onMessage: (value: string) => void;
}) {
  const fieldRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    if (!highlightField) return;
    fieldRefs.current[highlightField]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }, [highlightField, record.id]);

  return (
    <section className="record-deep-link-card">
      <header>
        <strong>Registro señalado para corrección</strong>
        <span className={`record-status ${record.status}`}>{record.status}</span>
      </header>
      <dl className="record-detail">
        {record.values.map((value) => (
          <div
            key={value.id}
            ref={(node) => { fieldRefs.current[value.field_name] = node; }}
            className={value.field_name === highlightField ? 'record-field-highlighted' : undefined}
          >
            <dt>{value.field_name}</dt>
            <dd>{formatValue(value.field_value_json, true)}</dd>
          </div>
        ))}
      </dl>
      <ReviewPanel projectId={projectId} record={record} onMessage={onMessage} />
    </section>
  );
}

function RecordTable({ templateId }: { templateId: string }) {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [records, setRecords] = useState<RuntimeRecord[]>([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [message, setMessage] = useState('Cargando registros...');
  const [deepLink] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return { recordId: params.get('recordId') ?? '', campo: params.get('campo') ?? '' };
  });
  const [deepLinkedRecord, setDeepLinkedRecord] = useState<RuntimeRecord | null>(null);
  const [deepLinkError, setDeepLinkError] = useState('');

  useEffect(() => {
    if (!deepLink.recordId) return;
    fetchRecord(deepLink.recordId)
      .then(setDeepLinkedRecord)
      .catch((error: Error) => setDeepLinkError(error.message));
  }, [deepLink.recordId]);

  useEffect(() => {
    let active = true;
    setMessage('Cargando registros...');
    searchTemplateRecords({ templateId, search: query.trim(), status, limit: PAGE_SIZE, offset })
      .then((page) => {
        if (!active) return;
        setRecords(page.items);
        setTotal(page.total);
        setMessage(page.total ? '' : 'Este formulario aún no tiene registros con esos filtros.');
      })
      .catch((error: Error) => active && setMessage(error.message));
    return () => {
      active = false;
    };
  }, [templateId, query, status, offset]);

  const fields = useMemo(() => Array.from(new Set(records.flatMap((record) => record.values.map((value) => value.field_name)))).slice(0, 5), [records]);
  const pageStart = total ? offset + 1 : 0;
  const pageEnd = Math.min(offset + records.length, total);

  async function exportCsv() {
    try {
      await downloadTemplateRecords(templateId, { search: query.trim(), status });
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible exportar.');
    }
  }

  return (
    <AppShell title="Registros del formulario">
      <main className="records-shell">
        {deepLinkedRecord ? (
          <DeepLinkedRecordCard projectId={projectId} record={deepLinkedRecord} highlightField={deepLink.campo} onMessage={setMessage} />
        ) : deepLinkError ? (
          <p role="alert">{deepLinkError}</p>
        ) : null}
        <div className="records-toolbar">
          <a href="/records">Volver a formularios</a>
          <div className="records-toolbar-actions">
            <input type="search" placeholder="Buscar por campo, valor, estado o usuario" value={query} onChange={(event) => { setQuery(event.target.value); setOffset(0); }} />
            <select aria-label="Filtrar por estado" value={status} onChange={(event) => { setStatus(event.target.value); setOffset(0); }}>
              <option value="">Todos los estados</option>
              <option value="draft">Borrador</option>
              <option value="submitted">Enviado</option>
              <option value="under_review">En revisión</option>
              <option value="tech_approved">Aprobado técnico</option>
              <option value="coordinator_approved">Aprobado coordinación</option>
              <option value="returned">Devuelto</option>
              <option value="corrected">Corregido</option>
              <option value="approved">Aprobado</option>
              <option value="rejected">Rechazado</option>
              <option value="cancelled">Cancelado</option>
              <option value="archived">Archivado</option>
            </select>
            <button onClick={() => void exportCsv()}>Exportar CSV</button>
          </div>
        </div>
        <div className="records-pagination" aria-live="polite">
          <span>{pageStart}-{pageEnd} de {total} registros</span>
          <button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Anterior</button>
          <button disabled={offset + PAGE_SIZE >= total} onClick={() => setOffset(offset + PAGE_SIZE)}>Siguiente</button>
        </div>
        {message ? <p role="status">{message}</p> : null}
        <div className="records-table-wrap">
          <table className="records-table">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Estado</th>
                {fields.map((field) => <th key={field}>{field}</th>)}
                <th>Detalle</th>
              </tr>
            </thead>
            <tbody>
              {records.map((record) => (
                <Fragment key={record.id}>
                  <tr>
                    <td>{new Date(record.created_at).toLocaleString()}</td>
                    <td><span className={`record-status ${record.status}`}>{record.status}</span></td>
                    {fields.map((field) => <td key={field}>{formatValue(record.values.find((value) => value.field_name === field)?.field_value_json)}</td>)}
                    <td><button onClick={() => setExpanded(expanded === record.id ? null : record.id)}>{expanded === record.id ? 'Cerrar' : 'Ver'}</button></td>
                  </tr>
                  {expanded === record.id ? (
                    <tr>
                      <td colSpan={fields.length + 3}>
                        <dl className="record-detail">
                          {record.values.map((value) => (
                            <div key={value.id}>
                              <dt>{value.field_name}</dt>
                              <dd>{formatValue(value.field_value_json, true)}</dd>
                            </div>
                          ))}
                        </dl>
                        <ReviewPanel projectId={projectId} record={record} onMessage={setMessage} />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </AppShell>
  );
}

function formatValue(raw?: string, detailed = false): string {
  if (!raw) return '—';
  try {
    const value = JSON.parse(raw);
    if (value === null || value === '') return '—';
    if (typeof value === 'boolean') return value ? 'Sí' : 'No';
    if (typeof value === 'string' || typeof value === 'number') return String(value);
    const text = JSON.stringify(value);
    return detailed ? text : `${text.slice(0, 60)}${text.length > 60 ? '…' : ''}`;
  } catch {
    return raw;
  }
}
