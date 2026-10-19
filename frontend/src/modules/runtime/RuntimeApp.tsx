import { useEffect, useRef, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { createParticipantInForm, fetchCaptureParticipants, fetchRuntimeTemplate, saveRuntimeRecord, startFormAssignment, toRuntimeValueList } from './api';
import { enqueueRecord } from '../offline/offlineSync';
import { isNetworkError, offlineCacheEnabled } from '../offline/offlineCache';
import { markCapturedOffline } from '../offline/offlinePackage';
import type { CaptureAssignment, EligibleParticipant } from './api';
import { ParticipantSummaryTable } from './ParticipantSummaryTable';
import { ParticipantPhoneCheck } from './ParticipantPhoneCheck';
import { RuntimeRenderer, themeStyle } from './RuntimeRenderer';
import { allComponents, isFieldVisible, resolveFormValues, stampInterviewDuration, validateFormValues } from './formLogic';
import { prefillParticipantAnswers } from './participantPrefill';
import { usePullData } from './pullData';
import { useRuntimeDraft } from './useRuntimeDraft';
import type { RuntimeFormValue, RuntimeTemplate } from './types';
import { useI18n } from '../../i18n';

function getTemplateIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const runtimeIndex = parts.indexOf('runtime');
  return runtimeIndex >= 0 && parts[runtimeIndex + 1] ? parts[runtimeIndex + 1] : '';
}

function reviewValue(value: RuntimeFormValue | undefined): string {
  if (value === undefined || value === null || value === '') return '—';
  if (Array.isArray(value)) return value.map((item) => reviewValue(item as RuntimeFormValue)).join(', ') || '—';
  if (typeof value === 'object') return '✓';
  return String(value);
}

export function RuntimeApp() {
  const { t } = useI18n();
  const [template, setTemplate] = useState<RuntimeTemplate | null>(null);
  const [status, setStatus] = useState(t('runtime.loadingForm'));
  const [participants, setParticipants] = useState<EligibleParticipant[]>([]);
  const [assignments, setAssignments] = useState<CaptureAssignment[]>([]);
  const [participantsReady, setParticipantsReady] = useState(false);
  const [participantKey, setParticipantKey] = useState('');
  const [keyField, setKeyField] = useState<'document_id' | 'external_code'>('external_code');
  const [accessMode, setAccessMode] = useState<'legacy' | 'open' | 'closed'>('legacy');
  const [assignmentReady, setAssignmentReady] = useState(false);
  const [showNewParticipant, setShowNewParticipant] = useState(false);
  const [newName, setNewName] = useState('');
  const [newMunicipality, setNewMunicipality] = useState('');
  const [newDepartment, setNewDepartment] = useState('');
  const [creatingParticipant, setCreatingParticipant] = useState(false);
  const [saving, setSaving] = useState(false);
  const [reviewing, setReviewing] = useState(false);
  // Inicio de la captura, para la duración de la entrevista (INTERVIEW_DURATION).
  const startedAt = useRef(Date.now());

  const templateId = getTemplateIdFromPath();
  const isPreview = new URLSearchParams(window.location.search).get('preview') === '1';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const initialParticipantId = new URLSearchParams(window.location.search).get('participantId') || '';
  const matchingParticipants = participants.filter((person) => participantKey.trim() && (person[keyField] || '').trim().toLocaleLowerCase() === participantKey.trim().toLocaleLowerCase());
  const matchingAssignments = assignments.filter((assignment) => participantKey.trim() && (assignment[keyField] || '').trim().toLocaleLowerCase() === participantKey.trim().toLocaleLowerCase());
  const existingAssignment = matchingAssignments.length === 1 && (matchingAssignments[0].record_id || ['completed', 'closed'].includes(matchingAssignments[0].status)) ? matchingAssignments[0] : null;
  const selectedParticipant = !existingAssignment && matchingParticipants.length === 1 ? matchingParticipants[0] : null;
  const participantId = selectedParticipant?.id || '';
  const { values, setValues, clearDraft, ready: draftReady, storageKey: draftKey } = useRuntimeDraft(`${templateId || 'sin-template'}${isPreview ? '-vista-previa' : ''}`, participantId);
  const { pulls, error: pullError, ready: pullsReady } = usePullData(template, values);

  useEffect(() => {
    if (!templateId || isPreview) return;
    fetchCaptureParticipants(templateId)
      .then(({ participants: rows, keyField: field, accessMode: mode, assignments: assigned }) => { setParticipants(rows); setAssignments(assigned); setKeyField(field); setAccessMode(mode); setParticipantsReady(true); const preselected = rows.find((person) => person.id === initialParticipantId); const existing = assigned.find((item) => item.participant_id === initialParticipantId); if (preselected?.[field] || existing?.[field]) setParticipantKey(preselected?.[field] || existing?.[field] || ''); })
      .catch((error: Error) => { setParticipantsReady(false); setStatus(error.message); });
  }, [templateId, isPreview]);

  useEffect(() => {
    if (!participantId || isPreview) { setAssignmentReady(false); return; }
    if (accessMode === 'legacy') { setAssignmentReady(true); return; }
    let active = true;
    setAssignmentReady(false);
    startFormAssignment(templateId, participantId)
      .then(() => { if (active) setAssignmentReady(true); })
      .catch((error: Error) => {
        if (!active) return;
        // Sin red en el escritorio: "iniciar" solo marca la actividad en curso;
        // el registro se valida igual en el servidor al sincronizar.
        if (isNetworkError(error) && offlineCacheEnabled()) setAssignmentReady(true);
        else setStatus(error.message);
      });
    return () => { active = false; };
  }, [templateId, participantId, accessMode, isPreview]);

  useEffect(() => {
    if (template) setValues((current) => resolveFormValues(template, current, pulls));
  }, [pulls, template]);

  useEffect(() => {
    if (!template || !selectedParticipant || !draftReady) return;
    setValues((current) => prefillParticipantAnswers(template, selectedParticipant, current, pulls));
  }, [template, participantId, draftReady]);

  useEffect(() => {
    if (!templateId) {
      setStatus(t('runtime.invalidUrl'));
      return;
    }

    fetchRuntimeTemplate(templateId)
      .then((result) => {
        setTemplate(result);
        setValues((current) => resolveFormValues(result, current));
        setStatus(isPreview ? t('runtime.previewMode') : t('runtime.draftActive'));
      })
      .catch((error: Error) => setStatus(error.message));
  }, [templateId]);

  function updateValue(fieldName: string, value: RuntimeFormValue) {
    setReviewing(false);
    setValues((current) => template ? resolveFormValues(template, { ...current, [fieldName]: value }, pulls) : { ...current, [fieldName]: value });
  }

  async function registerParticipant() {
    if (!participantKey.trim() || !newName.trim()) { setStatus(t('runtime.enterKeyAndName')); return; }
    setCreatingParticipant(true);
    try {
      await createParticipantInForm(templateId, { full_name: newName.trim(), document_id: keyField === 'document_id' ? participantKey.trim() : undefined,
        external_code: keyField === 'external_code' ? participantKey.trim() : undefined,
        department: newDepartment.trim(), municipality: newMunicipality.trim() });
      const refreshed = await fetchCaptureParticipants(templateId);
      setParticipants(refreshed.participants);
      setAssignments(refreshed.assignments);
      setShowNewParticipant(false);
      setNewName(''); setNewMunicipality(''); setNewDepartment('');
      setStatus(t('runtime.participantRegistered'));
    } catch (error) { setStatus(isNetworkError(error) ? t('offlineDesktop.needsConnection') : error instanceof Error ? error.message : t('runtime.registerFailed')); }
    finally { setCreatingParticipant(false); }
  }

  async function save() {
    if (saving) return;
    if (!template || !projectId) {
      setStatus(t('runtime.missingProjectOrTemplate'));
      return;
    }

    setSaving(true);
    try {
      if (!participantsReady) { setStatus(t('runtime.waitParticipants')); return; }
      if (!selectedParticipant) { setStatus(t('runtime.enterUniqueKey')); return; }
      if (!assignmentReady) { setStatus(t('runtime.waitAssignment')); return; }
      if (pullError || !pullsReady) { setStatus(pullError || t('runtime.waitCsv')); return; }
      const resolved = stampInterviewDuration(template, resolveFormValues(template, values, pulls), startedAt.current);
      const invalid = validateFormValues(template, resolved);
      if (invalid) { setStatus(invalid); return; }
      if (!reviewing) { setReviewing(true); setStatus(''); return; }
      let saved: { id: string };
      try {
        saved = await saveRuntimeRecord({ projectId, templateId: template.template_id, participantId, values: resolved });
      } catch (error) {
        // Solo los fallos de transporte entran en la cola. Los rechazos de
        // validacion o permisos necesitan una correccion del usuario.
        if (!(error instanceof TypeError)) throw error;
        const hasDeviceField = template.pages.flatMap((page) => page.sections)
          .flatMap((section) => section.rows).flatMap((row) => row.columns)
          .flatMap((column) => column.components)
          .some((component) => component.type.toUpperCase() === 'FINGERPRINT');
        if (hasDeviceField) {
          throw new Error(t('runtime.offlineNotAvailable'));
        }
        await enqueueRecord({ projectId, templateId: template.template_id, participantId, values: toRuntimeValueList(resolved) });
        await markCapturedOffline(projectId, template.template_id, participantId).catch(() => undefined);
        setAssignments((current) => current.map((assignment) => assignment.participant_id === participantId ? { ...assignment, status: 'completed' } : assignment));
        setReviewing(false);
        startedAt.current = Date.now();
        clearDraft();
        setParticipantKey('');
        setStatus(t('runtime.savedOffline'));
        return;
      }
      setAssignments((current) => current.map((assignment) => assignment.participant_id === participantId ? { ...assignment, status: 'completed', record_id: saved.id } : assignment));
      clearDraft();
      setParticipantKey('');
      setReviewing(false);
      startedAt.current = Date.now();
      setStatus(t('runtime.savedSuccess'));
    } catch (error) {
      setStatus(error instanceof Error ? error.message : t('runtime.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  if (!template) {
    return (
      <AppShell title={t('runtime.titleRuntime')}>
        <main className="runtime-shell"><p>{status}</p></main>
      </AppShell>
    );
  }

  return (
    <AppShell title={t('runtime.formViewTitle')}>
      <div className="runtime-themed" style={themeStyle(template.theme_json)}>
        <RuntimeRenderer template={template} projectId={projectId} values={values} onValueChange={updateValue} positionKey={isPreview ? undefined : draftKey}
          showQuestions={isPreview || Boolean(selectedParticipant && assignmentReady)}
          participantSection={!isPreview && <section className="runtime-participant-picker" aria-label={t('runtime.identifyParticipant')}>
            <h2>{t('runtime.identifyParticipant')}</h2>
            <p>{keyField === 'document_id' ? t('runtime.enterDocumentToStart') : t('runtime.enterCodeToStart')}</p>
            <label>{keyField === 'document_id' ? t('runtime.documentIdLabel') : t('runtime.participantCodeLabel')}
              <input type="text" autoComplete="off" value={participantKey} disabled={!participantsReady}
                onChange={(event) => { setParticipantKey(event.target.value); setShowNewParticipant(false); setReviewing(false); setStatus(t('runtime.draftActive')); }} />
            </label>
            {!participantsReady && <small>{t('runtime.loadingParticipants')}</small>}
            {participantsReady && !participants.length && accessMode !== 'open' && <p role="alert">{t('runtime.noEnabledParticipants')}</p>}
            {participantsReady && participantKey.trim() && !matchingParticipants.length && !matchingAssignments.length && <p role="alert">{t('runtime.participantNotFound')}</p>}
            {existingAssignment && <div className="runtime-existing-activity" role="alert">
              <strong>{t('runtime.existingRecord')}</strong>
              <span>{existingAssignment.participant_name} · {existingAssignment.status === 'closed' ? t('runtime.activityApprovedClosed') : t('runtime.responseAlreadySent')}</span>
              {existingAssignment.record_id && <a href={`/records/${templateId}?recordId=${existingAssignment.record_id}`}>{t('runtime.viewLinkedRecord')}</a>}
            </div>}
            {accessMode === 'open' && participantKey.trim() && !matchingParticipants.length && !matchingAssignments.length && hasAnyCurrentProjectPermission(['participants.create', 'identity.users.manage']) && <>
              <button type="button" onClick={() => setShowNewParticipant((value) => !value)}>{t('runtime.registerNewParticipant')}</button>
              {showNewParticipant && <div className="runtime-new-participant">
                <label>{t('runtime.fullName')}<input value={newName} onChange={(event) => setNewName(event.target.value)} /></label>
                <label>{t('runtime.department')}<input value={newDepartment} onChange={(event) => setNewDepartment(event.target.value)} /></label>
                <label>{t('runtime.municipality')}<input value={newMunicipality} onChange={(event) => setNewMunicipality(event.target.value)} /></label>
                <button type="button" disabled={creatingParticipant || !newName.trim()} onClick={() => void registerParticipant()}>{creatingParticipant ? t('runtime.registering') : t('runtime.saveAndContinue')}</button>
              </div>}
            </>}
            {(matchingParticipants.length > 1 || matchingAssignments.length > 1) && <p role="alert">{t('runtime.duplicateKeys')}</p>}
            {selectedParticipant && <ParticipantSummaryTable person={selectedParticipant} assignmentReady={assignmentReady || accessMode === 'legacy'} />}
            {selectedParticipant && accessMode !== 'legacy' && <ParticipantPhoneCheck key={selectedParticipant.id}
              person={selectedParticipant} templateId={templateId} assignmentReady={assignmentReady}
              onUpdated={(updated) => setParticipants((current) => current.map((person) => person.id === updated.id ? updated : person))} />}
          </section>}
          footerContent={<div className="runtime-actions">
            {reviewing && selectedParticipant && <section className="runtime-review"><h2>{t('runtime.reviewBeforeSubmit')}</h2><p>{selectedParticipant.full_name} · {selectedParticipant.document_id || selectedParticipant.external_code}</p><dl>{allComponents(template).filter((component) => isFieldVisible(component, values) && component.type !== 'HIDDEN').map((component) => <div key={component.id}><dt>{component.label}</dt><dd>{reviewValue(values[component.name])}</dd></div>)}</dl></section>}
            {!isPreview && selectedParticipant && assignmentReady && <button disabled={saving || !draftReady} onClick={save}>{saving ? t('runtime.saving') : reviewing ? t('runtime.confirmSubmit') : t('runtime.reviewResponse')}</button>}
            {reviewing && <button type="button" disabled={saving} onClick={() => setReviewing(false)}>{t('runtime.backToEdit')}</button>}
            {status ? <p>{status}</p> : null}{pullError && <p role="alert">{pullError}</p>}
          </div>} />
      </div>
    </AppShell>
  );
}
