import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
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
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [flows, setFlows] = useState<ApprovalFlow[]>([]);
  const [selected, setSelected] = useState<ApprovalFlowDetail | null>(null);
  const [templateFilter, setTemplateFilter] = useState('');
  const [flowName, setFlowName] = useState('');
  const [flowDescription, setFlowDescription] = useState('');
  const [flowTemplateId, setFlowTemplateId] = useState('');
  const [message, setMessage] = useState(t('admin.approvalFlows.loading'));

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
      setMessage(rows.length ? '' : t('admin.approvalFlows.noFlowsYet'));
      if (selectFirst && rows[0]) await selectFlow(rows[0].id);
      if (!rows.length) setSelected(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorLoadFlows'));
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
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorLoadDetail'));
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
      setMessage(t('admin.approvalFlows.flowCreated'));
      await selectFlow(created.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorCreateFlow'));
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
      setMessage(t('admin.approvalFlows.stepAdded'));
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorAddStep'));
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
      setMessage(t('admin.approvalFlows.flowUpdated'));
      await loadFlows(false);
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorUpdateFlow'));
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
      setMessage(t('admin.approvalFlows.stepUpdated'));
      cancelStepEdit();
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorUpdateStep'));
    }
  }

  async function toggleStepStatus(stepId: string, currentStatus: string) {
    if (!selected) return;
    try {
      await updateApprovalFlowStep(stepId, { status: currentStatus === 'active' ? 'inactive' : 'active' });
      setMessage(currentStatus === 'active' ? t('admin.approvalFlows.stepDeactivated') : t('admin.approvalFlows.stepReactivated'));
      await selectFlow(selected.id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.approvalFlows.errorUpdateStep'));
    }
  }

  useEffect(() => {
    void loadFlows(true);
  }, [projectId]);

  return (
    <AppShell title={t('admin.approvalFlows.title')}>
      <main className="approval-flows-shell">
        <section className="approval-flow-create">
          <h2>{t('admin.approvalFlows.newFlowTitle')}</h2>
          <p>{t('admin.approvalFlows.newFlowDescription')}</p>
          <label>{t('admin.approvalFlows.nameLabel')}<input value={flowName} onChange={(event) => setFlowName(event.target.value)} placeholder={t('admin.approvalFlows.namePlaceholder')} /></label>
          <label>{t('admin.approvalFlows.descriptionLabel')}<textarea rows={3} value={flowDescription} onChange={(event) => setFlowDescription(event.target.value)} placeholder={t('admin.approvalFlows.descriptionPlaceholder')} /></label>
          <label>{t('admin.approvalFlows.specificFormLabel')}<input value={flowTemplateId} onChange={(event) => setFlowTemplateId(event.target.value)} placeholder="template_id" /></label>
          <button className="primary" disabled={!flowName.trim()} onClick={() => void submitFlow()}>{t('admin.approvalFlows.createFlow')}</button>
          {message ? <p role="status">{message}</p> : null}
        </section>

        <section className="approval-flow-list">
          <header>
            <div>
              <h2>{t('admin.approvalFlows.configuredFlows')}</h2>
              <p>{t('admin.approvalFlows.priorityDescription')}</p>
            </div>
            <button onClick={() => void loadFlows(false)}>{t('admin.approvalFlows.refresh')}</button>
          </header>
          <label className="approval-flow-filter">
            {t('admin.approvalFlows.filterByForm')}
            <input value={templateFilter} onChange={(event) => setTemplateFilter(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void loadFlows(false); }} placeholder="template_id" />
          </label>
          <div className="approval-flow-cards">
            {flows.map((flow) => (
              <button className={selected?.id === flow.id ? 'selected' : ''} key={flow.id} onClick={() => void selectFlow(flow.id)}>
                <strong>{flow.name}</strong>
                <span>{flow.template_id ? t('admin.approvalFlows.formTemplate', { id: flow.template_id }) : t('admin.approvalFlows.projectGeneral')}</span>
                <small>{flow.status} · {t('admin.approvalFlows.version')} {flow.flow_version} · {flow.created_at ? new Date(flow.created_at).toLocaleString() : '—'}</small>
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
                  <p>{selected.description || t('admin.approvalFlows.noDescription')} · {t('admin.approvalFlows.version')} {selected.flow_version}</p>
                </div>
                <span>{selected.template_id ? t('admin.approvalFlows.specificForm') : t('admin.approvalFlows.fullProject')}</span>
              </header>

              <div className="approval-flow-edit-form">
                <h3>{t('admin.approvalFlows.editFlow')}</h3>
                <label>{t('admin.approvalFlows.nameLabel')}<input value={editName} onChange={(event) => setEditName(event.target.value)} /></label>
                <label>{t('admin.approvalFlows.descriptionLabel')}<textarea rows={2} value={editDescription} onChange={(event) => setEditDescription(event.target.value)} /></label>
                <label>{t('admin.approvalFlows.specificFormLabel')}<input value={editTemplateId} onChange={(event) => setEditTemplateId(event.target.value)} placeholder="template_id" /></label>
                <label>
                  {t('admin.approvalFlows.statusLabel')}
                  <select value={editStatus} onChange={(event) => setEditStatus(event.target.value)}>
                    <option value="active">{t('admin.approvalFlows.statusActive')}</option>
                    <option value="inactive">{t('admin.approvalFlows.statusInactive')}</option>
                  </select>
                </label>
                <button className="primary" disabled={!editName.trim()} onClick={() => void submitFlowUpdate()}>{t('admin.approvalFlows.saveChanges')}</button>
              </div>

              <div className="approval-flow-steps">
                {orderedSteps.length ? orderedSteps.map((step) => (
                  <article key={step.id}>
                    <strong>{step.step_order}. {step.name}</strong>
                    <span>{step.action_label} → {step.status_after}</span>
                    <small>{step.required_permission} · {step.status} · {step.approver_user_id ? t('admin.approvalFlows.approverUser', { id: step.approver_user_id }) : t('admin.approvalFlows.anyAuthorizedApprover')}</small>
                    <div className="approval-flow-step-actions">
                      <button onClick={() => startStepEdit(step)}>{t('admin.approvalFlows.editStep')}</button>
                      <button onClick={() => void toggleStepStatus(step.id, step.status)}>{step.status === 'active' ? t('admin.approvalFlows.deactivateStep') : t('admin.approvalFlows.reactivateStep')}</button>
                    </div>
                  </article>
                )) : <p>{t('admin.approvalFlows.noStepsYet')}</p>}
              </div>

              {editingStepId ? (
                <div className="approval-flow-step-edit-form">
                  <h3>{t('admin.approvalFlows.editStep')}</h3>
                  <label>{t('admin.approvalFlows.orderLabel')}<input type="number" min={1} value={editStepOrder} onChange={(event) => setEditStepOrder(Number(event.target.value))} /></label>
                  <label>{t('admin.approvalFlows.stepNameLabel')}<input value={editStepName} onChange={(event) => setEditStepName(event.target.value)} /></label>
                  <label>{t('admin.approvalFlows.buttonTextLabel')}<input value={editStepActionLabel} onChange={(event) => setEditStepActionLabel(event.target.value)} /></label>
                  <label>{t('admin.approvalFlows.technicalAction')}<input value={editStepAction} onChange={(event) => setEditStepAction(event.target.value)} /></label>
                  <label>{t('admin.approvalFlows.resultingStatus')}<input value={editStepStatusAfter} onChange={(event) => setEditStepStatusAfter(event.target.value)} /></label>
                  <label>{t('admin.approvalFlows.requiredPermission')}<input value={editStepPermission} onChange={(event) => setEditStepPermission(event.target.value)} /></label>
                  <label>{t('admin.approvalFlows.optionalApproverUser')}<input value={editStepApproverUserId} onChange={(event) => setEditStepApproverUserId(event.target.value)} placeholder="user_id" /></label>
                  <label>{t('admin.approvalFlows.optionalApproverRole')}<input value={editStepApproverRoleId} onChange={(event) => setEditStepApproverRoleId(event.target.value)} placeholder="role_id" /></label>
                  <label>
                    {t('admin.approvalFlows.stepStatusLabel')}
                    <select value={editStepStatus} onChange={(event) => setEditStepStatus(event.target.value)}>
                      <option value="active">{t('admin.approvalFlows.statusActive')}</option>
                      <option value="inactive">{t('admin.approvalFlows.statusInactive')}</option>
                    </select>
                  </label>
                  <label className="approval-flow-checkbox"><input type="checkbox" checked={editStepRequireAll} onChange={(event) => setEditStepRequireAll(event.target.checked)} /> {t('admin.approvalFlows.requireAllApprovers')}</label>
                  <div className="approval-flow-step-actions">
                    <button className="primary" disabled={!editStepName.trim() || !editStepActionLabel.trim() || !editStepAction.trim() || !editStepStatusAfter.trim() || !editStepPermission.trim()} onClick={() => void submitStepUpdate()}>{t('admin.approvalFlows.saveStep')}</button>
                    <button onClick={cancelStepEdit}>{t('admin.approvalFlows.cancel')}</button>
                  </div>
                </div>
              ) : null}

              <div className="approval-flow-step-form">
                <h3>{t('admin.approvalFlows.addStepNumber', { number: String(nextStepOrder(selected)) })}</h3>
                <label>
                  {t('admin.approvalFlows.quickTemplate')}
                  <select onChange={(event) => applyPreset(Number(event.target.value))} defaultValue="">
                    <option value="" disabled>{t('admin.approvalFlows.selectFrequentAction')}</option>
                    {DEFAULT_ACTIONS.map((item, index) => <option value={index} key={item.action}>{item.label}</option>)}
                  </select>
                </label>
                <label>{t('admin.approvalFlows.stepNameLabel')}<input value={stepName} onChange={(event) => setStepName(event.target.value)} placeholder={t('admin.approvalFlows.stepNamePlaceholder')} /></label>
                <label>{t('admin.approvalFlows.buttonTextLabel')}<input value={stepActionLabel} onChange={(event) => setStepActionLabel(event.target.value)} placeholder={t('admin.approvalFlows.buttonTextPlaceholder')} /></label>
                <label>{t('admin.approvalFlows.technicalAction')}<input value={stepAction} onChange={(event) => setStepAction(event.target.value)} placeholder="legal_approve" /></label>
                <label>{t('admin.approvalFlows.resultingStatus')}<input value={stepStatusAfter} onChange={(event) => setStepStatusAfter(event.target.value)} placeholder="legal_approved" /></label>
                <label>{t('admin.approvalFlows.requiredPermission')}<input value={stepPermission} onChange={(event) => setStepPermission(event.target.value)} placeholder="records.approve" /></label>
                <label>{t('admin.approvalFlows.optionalApproverUser')}<input value={stepApproverUserId} onChange={(event) => setStepApproverUserId(event.target.value)} placeholder="user_id" /></label>
                <label>{t('admin.approvalFlows.optionalApproverRole')}<input value={stepApproverRoleId} onChange={(event) => setStepApproverRoleId(event.target.value)} placeholder="role_id" /></label>
                <label className="approval-flow-checkbox"><input type="checkbox" checked={stepRequireAll} onChange={(event) => setStepRequireAll(event.target.checked)} /> {t('admin.approvalFlows.requireAllApprovers')}</label>
                <button className="primary" disabled={!stepName.trim() || !stepActionLabel.trim() || !stepAction.trim() || !stepStatusAfter.trim() || !stepPermission.trim()} onClick={() => void submitStep()}>{t('admin.approvalFlows.addStep')}</button>
              </div>
            </>
          ) : <p>{t('admin.approvalFlows.selectOrCreateFlow')}</p>}
        </section>
      </main>
    </AppShell>
  );
}
