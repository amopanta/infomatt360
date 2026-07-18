import { Fragment, useEffect, useMemo, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { applyReviewAction, correctRecordField, downloadTemplateRecords, fetchProjectTemplates, fetchRecord, fetchReviewActions, fetchReviewApprovalProgress, fetchReviewFlowComparison, fetchReviewNextActions, promoteRecordToParticipant, searchTemplateRecords } from './api';
import type { ReviewAction, ReviewApprovalProgress, ReviewFlowComparison, ReviewFlowSnapshot, ReviewNextAction, RuntimeRecord, TemplateSummary } from './api';
import { fetchActaTemplates, renderActaFromRecord } from '../acta/api';
import type { ActaTemplateSummary } from '../acta/types';
import { fetchRuntimeRecordChildren, fetchRuntimeTemplate, saveRuntimeChildRecord } from '../runtime/api';
import type { RuntimeRecordSummary } from '../runtime/api';
import { RuntimeField } from '../runtime/RuntimeField';
import { parseFieldConfig } from '../runtime/fieldConfig';
import type { RuntimeComponent, RuntimeFormValues, RuntimeTemplate } from '../runtime/types';
import { fetchProjectParticipants } from '../participants/api';
import type { Participant } from '../participants/api';

const REJECTION_STATUSES = new Set(['rejected', 'returned']);

const PAGE_SIZE = 25;

function templateIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[0] === 'records' ? parts[1] ?? '' : '';
}

const VOID_ACTION = { label: 'Anular', toStatus: 'voided', action: 'void' };

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
    VOID_ACTION,
  ],
  under_review: [
    { label: 'Aprobación técnica', toStatus: 'tech_approved', action: 'technical_approve' },
    { label: 'Aprobar', toStatus: 'approved', action: 'approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
    VOID_ACTION,
  ],
  tech_approved: [
    { label: 'Aprobación coordinador', toStatus: 'coordinator_approved', action: 'coordinator_approve' },
    { label: 'Aprobar final', toStatus: 'approved', action: 'approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
    VOID_ACTION,
  ],
  coordinator_approved: [
    { label: 'Aprobar final', toStatus: 'approved', action: 'final_approve' },
    { label: 'Devolver', toStatus: 'returned', action: 'return' },
    { label: 'Rechazar', toStatus: 'rejected', action: 'reject' },
    VOID_ACTION,
  ],
  returned: [
    { label: 'Marcar corregido', toStatus: 'corrected', action: 'mark_corrected' },
    VOID_ACTION,
  ],
  corrected: [
    { label: 'Reenviar a revisión', toStatus: 'under_review', action: 'resubmit_review' },
    VOID_ACTION,
  ],
  approved: [
    { label: 'Archivar', toStatus: 'archived', action: 'archive' },
    { label: 'Marcar sincronizado', toStatus: 'synced', action: 'mark_synced' },
    VOID_ACTION,
  ],
  rejected: [
    { label: 'Archivar', toStatus: 'archived', action: 'archive' },
    VOID_ACTION,
  ],
  archived: [VOID_ACTION],
  synced: [
    { label: 'Archivar', toStatus: 'archived', action: 'archive' },
    VOID_ACTION,
  ],
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

/** Ver docs/109 (constructor visual de actas, docs/96 item #4): genera un
 * PDF a partir de este registro usando una plantilla de acta ya diseñada
 * para su formulario. Reusa el mismo endpoint que el boton "Generar PDF de
 * prueba" del constructor -- no hay una vista previa aparte. */
function GenerateActaPanel({
  projectId,
  record,
  onMessage,
}: {
  projectId: string;
  record: RuntimeRecord;
  onMessage: (value: string) => void;
}) {
  const [templates, setTemplates] = useState<ActaTemplateSummary[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState('');
  const [generating, setGenerating] = useState(false);
  const canManageActa = hasAnyCurrentProjectPermission(['builder.write']);

  useEffect(() => {
    fetchActaTemplates(projectId)
      .then((rows) => setTemplates(rows.filter((template) => template.template_id === record.template_id)))
      .catch(() => setTemplates([]));
  }, [projectId, record.template_id]);

  async function generate() {
    if (!selectedTemplateId) return;
    setGenerating(true);
    try {
      await renderActaFromRecord(selectedTemplateId, record.id, 'acta');
      onMessage('Acta generada.');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible generar el acta.');
    } finally {
      setGenerating(false);
    }
  }

  if (templates.length === 0) {
    return canManageActa ? (
      <p className="acta-panel-empty">Este formulario aún no tiene plantillas de acta. <a href="/acta">Crear una</a>.</p>
    ) : null;
  }

  return (
    <div className="acta-panel">
      <select value={selectedTemplateId} onChange={(event) => setSelectedTemplateId(event.target.value)}>
        <option value="">Selecciona una plantilla de acta</option>
        {templates.map((template) => (
          <option key={template.id} value={template.id}>{template.name}</option>
        ))}
      </select>
      <button type="button" className="secondary" onClick={() => void generate()} disabled={!selectedTemplateId || generating}>
        {generating ? 'Generando...' : 'Generar acta'}
      </button>
    </div>
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

/** Solo se ofrece edicion en linea para valores simples (texto/numero/booleano).
 * Fotos, firmas, GPS u otros campos complejos se corrigen recapturando desde
 * el formulario, no con un input de texto generico. */
function isEditableScalar(raw: string): boolean {
  try {
    const value = JSON.parse(raw);
    return value === null || typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean';
  } catch {
    return false;
  }
}

function CorrectableField({
  record,
  value,
  onCorrected,
  onMessage,
}: {
  record: RuntimeRecord;
  value: { id: string; field_name: string; field_value_json: string };
  onCorrected: (record: RuntimeRecord) => void;
  onMessage: (value: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const canEditHere = record.status === 'returned';

  function startEditing() {
    let parsed: unknown = null;
    try {
      parsed = JSON.parse(value.field_value_json);
    } catch {
      parsed = null;
    }
    setDraft(parsed === null || parsed === undefined ? '' : String(parsed));
    setEditing(true);
  }

  async function submitCorrection() {
    setSaving(true);
    try {
      const updated = await correctRecordField({
        recordId: record.id,
        fieldName: value.field_name,
        fieldValueJson: JSON.stringify(draft),
        expectedLockVersion: record.lock_version,
      });
      onCorrected(updated);
      setEditing(false);
      onMessage('Corrección guardada.');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible guardar la corrección.');
    } finally {
      setSaving(false);
    }
  }

  if (!canEditHere) {
    return <dd>{formatValue(value.field_value_json, true)}</dd>;
  }

  if (!editing) {
    return (
      <dd>
        {formatValue(value.field_value_json, true)}
        {isEditableScalar(value.field_value_json) ? (
          <button className="record-field-edit-button" onClick={startEditing}>Corregir</button>
        ) : (
          <small className="record-field-uneditable"> (recaptura este campo desde el formulario original)</small>
        )}
      </dd>
    );
  }

  return (
    <dd>
      <input value={draft} onChange={(event) => setDraft(event.target.value)} disabled={saving} />
      <button disabled={saving} onClick={() => void submitCorrection()}>{saving ? 'Guardando…' : 'Guardar corrección'}</button>
      <button disabled={saving} onClick={() => setEditing(false)}>Cancelar</button>
    </dd>
  );
}

function flattenComponents(template: RuntimeTemplate): RuntimeComponent[] {
  return template.pages.flatMap((page) => page.sections.flatMap((section) => section.rows.flatMap((row) => row.columns.flatMap((column) => column.components))));
}

/** Gestion de filas hijas reales de un campo LINKED_SUBFORM (ver docs/97) --
 * a diferencia de un REPEAT embebido, cada fila es un RuntimeRecord propio
 * capturado con la plantilla hija, por eso necesita su propia consulta y
 * su propio formulario de alta en vez de venir ya incluido en `record.values`. */
function LinkedSubformField({
  projectId,
  parentRecordId,
  field,
  onMessage,
}: {
  projectId: string;
  parentRecordId: string;
  field: RuntimeComponent;
  onMessage: (value: string) => void;
}) {
  const config = parseFieldConfig(field.config_json);
  const childTemplateId = config.child_template_id;
  const [children, setChildren] = useState<RuntimeRecordSummary[]>([]);
  const [childTemplate, setChildTemplate] = useState<RuntimeTemplate | null>(null);
  const [values, setValues] = useState<RuntimeFormValues>({});
  const [adding, setAdding] = useState(false);
  const [saving, setSaving] = useState(false);

  async function loadChildren() {
    try {
      setChildren(await fetchRuntimeRecordChildren(parentRecordId, field.name));
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible consultar las filas hijas.');
    }
  }

  useEffect(() => { void loadChildren(); }, [parentRecordId, field.name]);
  useEffect(() => {
    if (!childTemplateId) return;
    fetchRuntimeTemplate(childTemplateId).then(setChildTemplate).catch(() => setChildTemplate(null));
  }, [childTemplateId]);

  const childComponents = childTemplate ? flattenComponents(childTemplate) : [];

  async function submitChild() {
    if (!childTemplateId) return;
    setSaving(true);
    try {
      await saveRuntimeChildRecord({ projectId, templateId: childTemplateId, parentRecordId, parentFieldName: field.name, values });
      setValues({});
      setAdding(false);
      await loadChildren();
      onMessage('Fila hija guardada.');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible guardar la fila hija.');
    } finally {
      setSaving(false);
    }
  }

  if (!childTemplateId) {
    return (
      <article className="record-linked-subform-card">
        <strong>{field.label}</strong>
        <p>Este campo aun no tiene una plantilla hija configurada en el constructor.</p>
      </article>
    );
  }

  return (
    <article className="record-linked-subform-card">
      <header>
        <strong>{field.label}</strong>
        <button type="button" onClick={() => setAdding((current) => !current)}>{adding ? 'Cancelar' : 'Agregar fila'}</button>
      </header>
      {children.length ? (
        <div className="records-table-wrap">
          <table className="records-table">
            <thead><tr>{childComponents.map((component) => <th key={component.id}>{component.label}</th>)}</tr></thead>
            <tbody>
              {children.map((child) => (
                <tr key={child.id}>
                  {childComponents.map((component) => <td key={component.id}>{formatValue(child.values.find((item) => item.field_name === component.name)?.field_value_json)}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : <p>Sin filas registradas todavia.</p>}
      {adding && childTemplate ? (
        <div className="record-linked-subform-form">
          {childComponents.map((component) => (
            <RuntimeField key={component.id} component={component} projectId={projectId} values={values} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />
          ))}
          <button type="button" className="primary" disabled={saving} onClick={() => void submitChild()}>{saving ? 'Guardando...' : 'Guardar fila'}</button>
        </div>
      ) : null}
    </article>
  );
}

function LinkedSubformSection({ projectId, record, onMessage }: { projectId: string; record: RuntimeRecord; onMessage: (value: string) => void }) {
  const [linkedFields, setLinkedFields] = useState<RuntimeComponent[]>([]);

  useEffect(() => {
    fetchRuntimeTemplate(record.template_id)
      .then((template) => setLinkedFields(flattenComponents(template).filter((component) => component.type.toUpperCase() === 'LINKED_SUBFORM')))
      .catch(() => setLinkedFields([]));
  }, [record.template_id]);

  if (!linkedFields.length) return null;

  return (
    <section className="record-linked-subforms">
      <h3>Subformularios enlazados</h3>
      {linkedFields.map((field) => <LinkedSubformField key={field.id} projectId={projectId} parentRecordId={record.id} field={field} onMessage={onMessage} />)}
    </section>
  );
}

/** Base abierta -> base cerrada (ver docs/99): un registro sin
 * `participant_id` viene de captura sin certeza previa de quien es la
 * persona. Aqui un revisor decide, explicitamente, enlazarlo a un
 * participante ya existente o crear uno nuevo -- nunca ocurre solo. */
function PromoteToParticipantPanel({
  projectId,
  record,
  onPromoted,
  onMessage,
}: {
  projectId: string;
  record: RuntimeRecord;
  onPromoted: (record: RuntimeRecord) => void;
  onMessage: (value: string) => void;
}) {
  const [participants, setParticipants] = useState<Participant[]>([]);
  const [mode, setMode] = useState<'link' | 'create'>('link');
  const [selectedParticipantId, setSelectedParticipantId] = useState('');
  const [fullName, setFullName] = useState('');
  const [documentId, setDocumentId] = useState('');
  const [externalCode, setExternalCode] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchProjectParticipants(projectId).then(setParticipants).catch(() => setParticipants([]));
  }, [projectId]);

  if (record.participant_id) return null;

  async function submit() {
    setSaving(true);
    try {
      await promoteRecordToParticipant({
        recordId: record.id,
        participantId: mode === 'link' ? selectedParticipantId : undefined,
        fullName: mode === 'create' ? fullName.trim() : undefined,
        documentId: mode === 'create' ? documentId.trim() || undefined : undefined,
        externalCode: mode === 'create' ? externalCode.trim() || undefined : undefined,
      });
      onPromoted(await fetchRecord(record.id));
      onMessage('Registro promovido a la base cerrada de participantes.');
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible promover el registro.');
    } finally {
      setSaving(false);
    }
  }

  const canSubmit = mode === 'link' ? Boolean(selectedParticipantId) : Boolean(fullName.trim());

  return (
    <section className="participant-promote-panel">
      <h3>Base abierta: sin participante enlazado</h3>
      <p>Este registro todavía no está asociado a ningún participante de la base cerrada. Enlázalo a uno existente o crea uno nuevo para consolidar la información.</p>
      <div className="participant-promote-mode">
        <label><input type="radio" checked={mode === 'link'} onChange={() => setMode('link')} /> Enlazar participante existente</label>
        <label><input type="radio" checked={mode === 'create'} onChange={() => setMode('create')} /> Crear participante nuevo</label>
      </div>
      {mode === 'link' ? (
        <label>Participante
          <select value={selectedParticipantId} onChange={(event) => setSelectedParticipantId(event.target.value)}>
            <option value="">Selecciona un participante</option>
            {participants.map((participant) => (
              <option key={participant.id} value={participant.id}>{participant.full_name}{participant.document_id ? ` (${participant.document_id})` : ''}</option>
            ))}
          </select>
        </label>
      ) : (
        <div className="participant-promote-fields">
          <label>Nombre completo<input value={fullName} onChange={(event) => setFullName(event.target.value)} /></label>
          <label>Documento<input value={documentId} onChange={(event) => setDocumentId(event.target.value)} /></label>
          <label>Código externo<input value={externalCode} onChange={(event) => setExternalCode(event.target.value)} /></label>
        </div>
      )}
      <button type="button" className="primary" disabled={saving || !canSubmit} onClick={() => void submit()}>
        {saving ? 'Guardando…' : 'Promover a participante'}
      </button>
    </section>
  );
}

function DeepLinkedRecordCard({
  projectId,
  record,
  highlightField,
  onRecordUpdated,
  onMessage,
}: {
  projectId: string;
  record: RuntimeRecord;
  highlightField: string;
  onRecordUpdated: (record: RuntimeRecord) => void;
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
            <CorrectableField record={record} value={value} onCorrected={onRecordUpdated} onMessage={onMessage} />
          </div>
        ))}
      </dl>
      <PromoteToParticipantPanel projectId={projectId} record={record} onPromoted={onRecordUpdated} onMessage={onMessage} />
      <LinkedSubformSection projectId={projectId} record={record} onMessage={onMessage} />
      <ReviewPanel projectId={projectId} record={record} onMessage={onMessage} />
      <GenerateActaPanel projectId={projectId} record={record} onMessage={onMessage} />
    </section>
  );
}

function RecordTable({ templateId }: { templateId: string }) {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [records, setRecords] = useState<RuntimeRecord[]>([]);
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState('');
  const [unlinkedOnly, setUnlinkedOnly] = useState(false);
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
    searchTemplateRecords({ templateId, search: query.trim(), status, unlinkedOnly, limit: PAGE_SIZE, offset })
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
  }, [templateId, query, status, unlinkedOnly, offset]);

  function updateRecordInList(updated: RuntimeRecord) {
    setRecords((current) => current.map((record) => record.id === updated.id ? updated : record));
  }

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
          <DeepLinkedRecordCard projectId={projectId} record={deepLinkedRecord} highlightField={deepLink.campo} onRecordUpdated={setDeepLinkedRecord} onMessage={setMessage} />
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
              <option value="synced">Sincronizado</option>
              <option value="voided">Anulado</option>
            </select>
            <label className="records-unlinked-filter">
              <input type="checkbox" checked={unlinkedOnly} onChange={(event) => { setUnlinkedOnly(event.target.checked); setOffset(0); }} />
              Sin participante enlazado
            </label>
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
                        <PromoteToParticipantPanel projectId={projectId} record={record} onPromoted={updateRecordInList} onMessage={setMessage} />
                        <LinkedSubformSection projectId={projectId} record={record} onMessage={setMessage} />
                        <ReviewPanel projectId={projectId} record={record} onMessage={setMessage} />
                        <GenerateActaPanel projectId={projectId} record={record} onMessage={setMessage} />
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
