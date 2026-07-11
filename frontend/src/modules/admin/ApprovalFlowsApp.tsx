import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { addApprovalFlowStep, createApprovalFlow, fetchApprovalFlowDetail, fetchApprovalFlows, updateApprovalFlow, updateApprovalFlowStep } from './approvalFlowsApi';
import type { ApprovalFlow, ApprovalFlowDetail, ApprovalFlowStep } from './approvalFlowsApi';

const DEFAULT_ACTIONS = [
  { label: 'Enviar a revisión', action: 'start_review', status: 'under_review', permission: 'records.review' },
  { label: 'Aprobación técnica', action: 'technical_approve', status: 'tech_approved', permission: 'records.review' },
  { label: 'Aprobación coordinador', action: 'coordinator_approve', status: 'coordinator_approved', permission: 'records.coordinate' },
  { label: 'Aprobar final', action: 'final_approve', status: 'approved', permission: 'records.approve' },
  { label: 'Devolver', action: 'return', status: 'returned', permission: 'records.review' },
  { label: 'Rechazar', action: 'reject', status: 'rejected', permission: 'records.approve' },
];

function nextStepOrder(detail: ApprovalFlowDetail | null) {
  if (!detail?.steps.length) return 1;
  return Math.max(...detail.steps.map((step) => step.step_order)) + 1;
}

export function ApprovalFlowsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [flows, setFlows] = useState<ApprovalFlow[]>([]);
  const [selected, setSelected] = useState<ApprovalFlowDetail | null>(null);
  const [templateFilter, setTemplateFilter] = useState('');
  const [flowName, setFlowName] = useState('');
  const [flowDescription, setFlowDescription] = useState('');
  const [flowTemplateId, setFlowTemplateId] = useState('');
  const [message, setMessage] = useState('Cargando flujos de aprobación...');

  const [stepName, setStepName] = useState('');
  const [stepActionLabel, setStepActionLabel] = useState('');
  const [stepAction, setStepAction] = useState('');
  const [stepStatusAfter, setStepStatusAfter] = useState('');
  const [stepPermission, setStepPermission] = useState('records.review');
  const [stepApproverUserId, setStepApproverUserId] = useState('');
  const [stepApproverRoleId, setStepApproverRoleId] = useState('');
  const [stepRequireAll, setStepRequireAll] = useState(false);

  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editTemplateId, setEditTemplateId] = useState('');
  const [editStatus, setEditStatus] = useState('active');

  const [editingStepId, setEditingStepId] = useState('');
  const [editStepOrder, setEditStepOrder] = useState(1);
  const [editStepName, setEditStepName] = useState('');
  const [editStepActionLabel, setEditStepActionLabel] = useState('');
  const [editStepAction, setEditStepAction] = useState('');
  const [editStepStatusAfter, setEditStepStatusAfter] = useState('');
  const [editStepPermission, setEditStepPermission] = useState('');
  const [editStepApproverUserId, setEditStepApproverUserId] = useState('');
  const [editStepApproverRoleId, setEditStepApproverRoleId] = useState('');
  const [editStepRequireAll, setEditStepRequireAll] = useState(false);
  const [editStepStatus, setEditStepStatus] = useState('active');

  const orderedSteps = useMemo(
    () => [...(selected?.steps ?? [])].sort((a, b) => a.step_order - b.step_order),
    [selected],
  );

  async function loadFlows(selectFirst = false) {
    try {
      const rows = await fetchApprovalFlows(projectId, templateFilter);
      setFlows(rows);
      setMessage(rows.length ? '' : 'Aún no hay flujos configurados para este proyecto.');
      if (selectFirst && rows[0]) await selectFlow(rows[0].id);
      if (!rows.length) setSelected(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar los flujos.');
    }
  }

  async function selectFlow(flowId: string) {
    try {
      const detail = await fetchApprovalFlowDetail(flowId);
      setSelected(detail);
      setEditName(detail.name);
      setEditDescription(detail.description ?? '');
      setEditTemplateId(detail.template_id ?? '');
      setEditStatus(detail.status);
      cancelStepEdit();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar el detalle del flujo.');
    }
  }

  async function submitFlow() {
    try {
      const created = await createApprovalFlow({
        projectId,
        templateId: flowTemplateId,
        name: flowName.trim(),
        description: flowDescription.trim(),
        status: 'active',
      });
      setFlows((current) => [created, ...current]);
      setFlowName('');
      setFlowDescription('');
      setFlowTemplateId('');
      setMessage('Flujo creado. Ahora puedes agregar sus pasos.');
      await selectFlow(created.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear el flujo.');
    }
  }

  function applyPreset(index: number) {
    const preset = DEFAULT_ACTIONS[index];
    if (!preset) return;
    setStepName(preset.label);
    setStepActionLabel(preset.label);
    setStepAction(preset.action);
    setStepStatusAfter(preset.status);
    setStepPermission(preset.permission);
  }

  async function submitStep() {
    if (!selected) return;
    try {
      await addApprovalFlowStep({
        flowId: selected.id,
        stepOrder: nextStepOrder(selected),
        name: stepName.trim(),
        actionLabel: stepActionLabel.trim(),
        action: stepAction.trim(),
        statusAfter: stepStatusAfter.trim(),
        requiredPermission: stepPermission.trim(),
        approverUserId: stepApproverUserId,
        approverRoleId: stepApproverRoleId,
        requireAll: stepRequireAll,
        status: 'active',
      });
      setStepName('');
      setStepActionLabel('');
      setStepAction('');
      setStepStatusAfter('');
      setStepPermission('records.review');
      setStepApproverUserId('');
      setStepApproverRoleId('');
      setStepRequireAll(false);
      setMessage('Paso agregado al flujo.');
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible agregar el paso.');
    }
  }

  async function submitFlowUpdate() {
    if (!selected) return;
    try {
      await updateApprovalFlow(selected.id, {
        name: editName.trim(),
        description: editDescription.trim() || null,
        templateId: editTemplateId.trim() || null,
        status: editStatus,
      });
      setMessage('Flujo actualizado.');
      await loadFlows(false);
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el flujo.');
    }
  }

  function startStepEdit(step: ApprovalFlowStep) {
    setEditingStepId(step.id);
    setEditStepOrder(step.step_order);
    setEditStepName(step.name);
    setEditStepActionLabel(step.action_label);
    setEditStepAction(step.action);
    setEditStepStatusAfter(step.status_after);
    setEditStepPermission(step.required_permission);
    setEditStepApproverUserId(step.approver_user_id ?? '');
    setEditStepApproverRoleId(step.approver_role_id ?? '');
    setEditStepRequireAll(step.require_all);
    setEditStepStatus(step.status);
  }

  function cancelStepEdit() {
    setEditingStepId('');
    setEditStepOrder(1);
    setEditStepName('');
    setEditStepActionLabel('');
    setEditStepAction('');
    setEditStepStatusAfter('');
    setEditStepPermission('');
    setEditStepApproverUserId('');
    setEditStepApproverRoleId('');
    setEditStepRequireAll(false);
    setEditStepStatus('active');
  }

  async function submitStepUpdate() {
    if (!selected || !editingStepId) return;
    try {
      await updateApprovalFlowStep(editingStepId, {
        stepOrder: editStepOrder,
        name: editStepName.trim(),
        actionLabel: editStepActionLabel.trim(),
        action: editStepAction.trim(),
        statusAfter: editStepStatusAfter.trim(),
        requiredPermission: editStepPermission.trim(),
        approverUserId: editStepApproverUserId.trim() || null,
        approverRoleId: editStepApproverRoleId.trim() || null,
        requireAll: editStepRequireAll,
        status: editStepStatus,
      });
      setMessage('Paso actualizado.');
      cancelStepEdit();
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el paso.');
    }
  }

  async function toggleStepStatus(stepId: string, currentStatus: string) {
    if (!selected) return;
    try {
      await updateApprovalFlowStep(stepId, { status: currentStatus === 'active' ? 'inactive' : 'active' });
      setMessage(currentStatus === 'active' ? 'Paso desactivado.' : 'Paso reactivado.');
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el paso.');
    }
  }

  useEffect(() => {
    void loadFlows(true);
  }, [projectId]);

  return (
    <AppShell title="Flujos de aprobación">
      <main className="approval-flows-shell">
        <section className="approval-flow-create">
          <h2>Nuevo flujo</h2>
          <p>Define aprobadores por proyecto o por formulario sin tocar código.</p>
          <label>Nombre<input value={flowName} onChange={(event) => setFlowName(event.target.value)} placeholder="Flujo HSEQ" /></label>
          <label>Descripción<textarea rows={3} value={flowDescription} onChange={(event) => setFlowDescription(event.target.value)} placeholder="Describe cuándo aplica este flujo." /></label>
          <label>Formulario específico opcional<input value={flowTemplateId} onChange={(event) => setFlowTemplateId(event.target.value)} placeholder="template_id" /></label>
          <button className="primary" disabled={!flowName.trim()} onClick={() => void submitFlow()}>Crear flujo</button>
          {message ? <p role="status">{message}</p> : null}
        </section>

        <section className="approval-flow-list">
          <header>
            <div>
              <h2>Flujos configurados</h2>
              <p>El backend prioriza formulario, luego proyecto, y finalmente el flujo predeterminado.</p>
            </div>
            <button onClick={() => void loadFlows(false)}>Actualizar</button>
          </header>
          <label className="approval-flow-filter">
            Filtrar por formulario
            <input value={templateFilter} onChange={(event) => setTemplateFilter(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void loadFlows(false); }} placeholder="template_id" />
          </label>
          <div className="approval-flow-cards">
            {flows.map((flow) => (
              <button className={selected?.id === flow.id ? 'selected' : ''} key={flow.id} onClick={() => void selectFlow(flow.id)}>
                <strong>{flow.name}</strong>
                <span>{flow.template_id ? `Formulario: ${flow.template_id}` : 'General del proyecto'}</span>
                <small>{flow.status} · versión {flow.flow_version} · {flow.created_at ? new Date(flow.created_at).toLocaleString() : '—'}</small>
              </button>
            ))}
          </div>
        </section>

        <section className="approval-flow-detail">
          {selected ? (
            <>
              <header>
                <div>
                  <h2>{selected.name}</h2>
                  <p>{selected.description || 'Sin descripción'} · versión {selected.flow_version}</p>
                </div>
                <span>{selected.template_id ? 'Formulario específico' : 'Proyecto completo'}</span>
              </header>

              <div className="approval-flow-edit-form">
                <h3>Editar flujo</h3>
                <label>Nombre<input value={editName} onChange={(event) => setEditName(event.target.value)} /></label>
                <label>Descripción<textarea rows={2} value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label>
                <label>Formulario específico opcional<input value={editTemplateId} onChange={(event) => setEditTemplateId(event.target.value)} placeholder="template_id" /></label>
                <label>
                  Estado
                  <select value={editStatus} onChange={(event) => setEditStatus(event.target.value)}>
                    <option value="active">Activo</option>
                    <option value="inactive">Inactivo</option>
                  </select>
                </label>
                <button className="primary" disabled={!editName.trim()} onClick={() => void submitFlowUpdate()}>Guardar cambios</button>
              </div>

              <div className="approval-flow-steps">
                {orderedSteps.length ? orderedSteps.map((step) => (
                  <article key={step.id}>
                    <strong>{step.step_order}. {step.name}</strong>
                    <span>{step.action_label} → {step.status_after}</span>
                    <small>{step.required_permission} · {step.status} · {step.approver_user_id ? `Usuario: ${step.approver_user_id}` : 'Cualquier aprobador autorizado'}</small>
                    <div className="approval-flow-step-actions">
                      <button onClick={() => startStepEdit(step)}>Editar paso</button>
                      <button onClick={() => void toggleStepStatus(step.id, step.status)}>{step.status === 'active' ? 'Desactivar paso' : 'Reactivar paso'}</button>
                    </div>
                  </article>
                )) : <p>Este flujo aún no tiene pasos. Agrega el primer aprobador.</p>}
              </div>

              {editingStepId ? (
                <div className="approval-flow-step-edit-form">
                  <h3>Editar paso</h3>
                  <label>Orden<input type="number" min={1} value={editStepOrder} onChange={(event) => setEditStepOrder(Number(event.target.value))} /></label>
                  <label>Nombre del paso<input value={editStepName} onChange={(event) => setEditStepName(event.target.value)} /></label>
                  <label>Texto del botón<input value={editStepActionLabel} onChange={(event) => setEditStepActionLabel(event.target.value)} /></label>
                  <label>Acción técnica<input value={editStepAction} onChange={(event) => setEditStepAction(event.target.value)} /></label>
                  <label>Estado resultante<input value={editStepStatusAfter} onChange={(event) => setEditStepStatusAfter(event.target.value)} /></label>
                  <label>Permiso requerido<input value={editStepPermission} onChange={(event) => setEditStepPermission(event.target.value)} /></label>
                  <label>Usuario aprobador opcional<input value={editStepApproverUserId} onChange={(event) => setEditStepApproverUserId(event.target.value)} placeholder="user_id" /></label>
                  <label>Rol aprobador opcional<input value={editStepApproverRoleId} onChange={(event) => setEditStepApproverRoleId(event.target.value)} placeholder="role_id" /></label>
                  <label>
                    Estado del paso
                    <select value={editStepStatus} onChange={(event) => setEditStepStatus(event.target.value)}>
                      <option value="active">Activo</option>
                      <option value="inactive">Inactivo</option>
                    </select>
                  </label>
                  <label className="approval-flow-checkbox"><input type="checkbox" checked={editStepRequireAll} onChange={(event) => setEditStepRequireAll(event.target.checked)} /> Requerir todos los aprobadores configurados</label>
                  <div className="approval-flow-step-actions">
                    <button className="primary" disabled={!editStepName.trim() || !editStepActionLabel.trim() || !editStepAction.trim() || !editStepStatusAfter.trim() || !editStepPermission.trim()} onClick={() => void submitStepUpdate()}>Guardar paso</button>
                    <button onClick={cancelStepEdit}>Cancelar</button>
                  </div>
                </div>
              ) : null}

              <div className="approval-flow-step-form">
                <h3>Agregar paso #{nextStepOrder(selected)}</h3>
                <label>
                  Plantilla rápida
                  <select onChange={(event) => applyPreset(Number(event.target.value))} defaultValue="">
                    <option value="" disabled>Selecciona una acción frecuente</option>
                    {DEFAULT_ACTIONS.map((item, index) => <option value={index} key={item.action}>{item.label}</option>)}
                  </select>
                </label>
                <label>Nombre del paso<input value={stepName} onChange={(event) => setStepName(event.target.value)} placeholder="Revisión jurídica" /></label>
                <label>Texto del botón<input value={stepActionLabel} onChange={(event) => setStepActionLabel(event.target.value)} placeholder="Aprobar jurídica" /></label>
                <label>Acción técnica<input value={stepAction} onChange={(event) => setStepAction(event.target.value)} placeholder="legal_approve" /></label>
                <label>Estado resultante<input value={stepStatusAfter} onChange={(event) => setStepStatusAfter(event.target.value)} placeholder="legal_approved" /></label>
                <label>Permiso requerido<input value={stepPermission} onChange={(event) => setStepPermission(event.target.value)} placeholder="records.approve" /></label>
                <label>Usuario aprobador opcional<input value={stepApproverUserId} onChange={(event) => setStepApproverUserId(event.target.value)} placeholder="user_id" /></label>
                <label>Rol aprobador opcional<input value={stepApproverRoleId} onChange={(event) => setStepApproverRoleId(event.target.value)} placeholder="role_id" /></label>
                <label className="approval-flow-checkbox"><input type="checkbox" checked={stepRequireAll} onChange={(event) => setStepRequireAll(event.target.checked)} /> Requerir todos los aprobadores configurados</label>
                <button className="primary" disabled={!stepName.trim() || !stepActionLabel.trim() || !stepAction.trim() || !stepStatusAfter.trim() || !stepPermission.trim()} onClick={() => void submitStep()}>Agregar paso</button>
              </div>
            </>
          ) : <p>Selecciona o crea un flujo para administrar sus pasos.</p>}
        </section>
      </main>
    </AppShell>
  );
}
