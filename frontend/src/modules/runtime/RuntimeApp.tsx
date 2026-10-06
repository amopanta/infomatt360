import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY, hasAnyCurrentProjectPermission } from '../auth/session';
import { createParticipantInForm, fetchCaptureParticipants, fetchRuntimeTemplate, saveRuntimeRecord, startFormAssignment, toRuntimeValueList } from './api';
import { enqueueRecord } from '../offline/offlineSync';
import type { CaptureAssignment, EligibleParticipant } from './api';
import { ParticipantSummaryTable } from './ParticipantSummaryTable';
import { ParticipantPhoneCheck } from './ParticipantPhoneCheck';
import { RuntimeRenderer, themeStyle } from './RuntimeRenderer';
import { resolveFormValues, validateFormValues } from './formLogic';
import { usePullData } from './pullData';
import { useRuntimeDraft } from './useRuntimeDraft';
import type { RuntimeFormValue, RuntimeTemplate } from './types';

function getTemplateIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const runtimeIndex = parts.indexOf('runtime');
  return runtimeIndex >= 0 && parts[runtimeIndex + 1] ? parts[runtimeIndex + 1] : '';
}

export function RuntimeApp() {
  const [template, setTemplate] = useState<RuntimeTemplate | null>(null);
  const [status, setStatus] = useState('Cargando formulario...');
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

  const templateId = getTemplateIdFromPath();
  const isPreview = new URLSearchParams(window.location.search).get('preview') === '1';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const initialParticipantId = new URLSearchParams(window.location.search).get('participantId') || '';
  const matchingParticipants = participants.filter((person) => participantKey.trim() && (person[keyField] || '').trim().toLocaleLowerCase() === participantKey.trim().toLocaleLowerCase());
  const matchingAssignments = assignments.filter((assignment) => participantKey.trim() && (assignment[keyField] || '').trim().toLocaleLowerCase() === participantKey.trim().toLocaleLowerCase());
  const existingAssignment = matchingAssignments.length === 1 && (matchingAssignments[0].record_id || ['completed', 'closed'].includes(matchingAssignments[0].status)) ? matchingAssignments[0] : null;
  const selectedParticipant = !existingAssignment && matchingParticipants.length === 1 ? matchingParticipants[0] : null;
  const participantId = selectedParticipant?.id || '';
  const { values, setValues, clearDraft } = useRuntimeDraft(`${templateId || 'sin-template'}${isPreview ? '-vista-previa' : ''}`);
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
      .catch((error: Error) => { if (active) setStatus(error.message); });
    return () => { active = false; };
  }, [templateId, participantId, accessMode, isPreview]);

  useEffect(() => {
    if (template) setValues((current) => resolveFormValues(template, current, pulls));
  }, [pulls, template]);

  useEffect(() => {
    if (!templateId) {
      setStatus('Debe abrir una URL con formato /runtime/{template_id}.');
      return;
    }

    fetchRuntimeTemplate(templateId)
      .then((result) => {
        setTemplate(result);
        setValues((current) => resolveFormValues(result, current));
        setStatus(isPreview ? 'Vista previa: puedes probar las preguntas; aquí no se guarda ninguna respuesta.' : 'Borrador local activo.');
      })
      .catch((error: Error) => setStatus(error.message));
  }, [templateId]);

  function updateValue(fieldName: string, value: RuntimeFormValue) {
    setValues((current) => template ? resolveFormValues(template, { ...current, [fieldName]: value }, pulls) : { ...current, [fieldName]: value });
  }

  async function registerParticipant() {
    if (!participantKey.trim() || !newName.trim()) { setStatus('Ingresa la llave y el nombre del participante.'); return; }
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
      setStatus('Participante registrado y asignado a tu usuario.');
    } catch (error) { setStatus(error instanceof Error ? error.message : 'No fue posible registrar el participante.'); }
    finally { setCreatingParticipant(false); }
  }

  async function save() {
    if (saving) return;
    if (!template || !projectId) {
      setStatus('Falta proyecto activo en la sesion o plantilla runtime.');
      return;
    }

    setSaving(true);
    try {
      if (!participantsReady) { setStatus('Espera a que se carguen los participantes asociados.'); return; }
      if (!selectedParticipant) { setStatus('Ingresa una llave que identifique a un solo participante habilitado.'); return; }
      if (!assignmentReady) { setStatus('Espera a que se confirme la asignación de este participante.'); return; }
      if (pullError || !pullsReady) { setStatus(pullError || 'Espera a que termine la consulta del CSV.'); return; }
      const resolved = resolveFormValues(template, values, pulls);
      const invalid = validateFormValues(template, resolved);
      if (invalid) { setStatus(invalid); return; }
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
          throw new Error('Este formulario requiere verificar el dispositivo en línea; el envío sin conexión no está disponible. Conservamos tu borrador local.');
        }
        await enqueueRecord({ projectId, templateId: template.template_id, participantId, values: toRuntimeValueList(resolved) });
        clearDraft();
        setParticipantKey('');
        setStatus('Respuesta guardada en este dispositivo. Se enviará al recuperar la conexión; verifica el estado de sincronización.');
        return;
      }
      setAssignments((current) => current.map((assignment) => assignment.participant_id === participantId ? { ...assignment, status: 'completed', record_id: saved.id } : assignment));
      clearDraft();
      setParticipantKey('');
      setStatus('Respuesta guardada y asociada correctamente.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'No fue posible guardar la respuesta.');
    } finally {
      setSaving(false);
    }
  }

  if (!template) {
    return (
      <AppShell title="Runtime">
        <main className="runtime-shell"><p>{status}</p></main>
      </AppShell>
    );
  }

  return (
    <AppShell title="Vista de Formulario">
      <div className="runtime-themed" style={themeStyle(template.theme_json)}>
        <RuntimeRenderer template={template} projectId={projectId} values={values} onValueChange={updateValue}
          showQuestions={isPreview || Boolean(selectedParticipant && assignmentReady)}
          participantSection={!isPreview && <section className="runtime-participant-picker" aria-label="Identificar participante">
            <h2>Identificar participante</h2>
            <p>Ingresa {keyField === 'document_id' ? 'el número de documento o cédula' : 'el código del participante'} para comenzar.</p>
            <label>{keyField === 'document_id' ? 'Número de documento o cédula' : 'Código del participante'}
              <input type="text" autoComplete="off" value={participantKey} disabled={!participantsReady}
                onChange={(event) => { setParticipantKey(event.target.value); setShowNewParticipant(false); setStatus('Borrador local activo.'); }} />
            </label>
            {!participantsReady && <small>Cargando participantes...</small>}
            {participantsReady && !participants.length && accessMode !== 'open' && <p role="alert">No hay participantes habilitados para este formulario. Solicita al administrador que los asigne.</p>}
            {participantsReady && participantKey.trim() && !matchingParticipants.length && !matchingAssignments.length && <p role="alert">No se encontró un participante asignado a tu usuario con esa llave.</p>}
            {existingAssignment && <div className="runtime-existing-activity" role="alert">
              <strong>Este participante ya tiene un registro asociado a esta actividad.</strong>
              <span>{existingAssignment.participant_name} · {existingAssignment.status === 'closed' ? 'Actividad aprobada y cerrada' : 'Respuesta ya enviada'}</span>
              {existingAssignment.record_id && <a href={`/records/${templateId}?recordId=${existingAssignment.record_id}`}>Ver registro asociado</a>}
            </div>}
            {accessMode === 'open' && participantKey.trim() && !matchingParticipants.length && !matchingAssignments.length && hasAnyCurrentProjectPermission(['participants.create', 'identity.users.manage']) && <>
              <button type="button" onClick={() => setShowNewParticipant((value) => !value)}>Registrar participante nuevo</button>
              {showNewParticipant && <div className="runtime-new-participant">
                <label>Nombre completo<input value={newName} onChange={(event) => setNewName(event.target.value)} /></label>
                <label>Departamento<input value={newDepartment} onChange={(event) => setNewDepartment(event.target.value)} /></label>
                <label>Municipio<input value={newMunicipality} onChange={(event) => setNewMunicipality(event.target.value)} /></label>
                <button type="button" disabled={creatingParticipant || !newName.trim()} onClick={() => void registerParticipant()}>{creatingParticipant ? 'Registrando...' : 'Guardar y continuar'}</button>
              </div>}
            </>}
            {(matchingParticipants.length > 1 || matchingAssignments.length > 1) && <p role="alert">Esta llave coincide con varias personas. Solicita al administrador corregir los documentos o códigos duplicados.</p>}
            {selectedParticipant && <ParticipantSummaryTable person={selectedParticipant} assignmentReady={assignmentReady || accessMode === 'legacy'} />}
            {selectedParticipant && accessMode !== 'legacy' && <ParticipantPhoneCheck key={selectedParticipant.id}
              person={selectedParticipant} templateId={templateId} assignmentReady={assignmentReady}
              onUpdated={(updated) => setParticipants((current) => current.map((person) => person.id === updated.id ? updated : person))} />}
          </section>}
          footerContent={<div className="runtime-actions">
            {!isPreview && selectedParticipant && assignmentReady && <button disabled={saving} onClick={save}>{saving ? 'Guardando...' : 'Guardar respuesta'}</button>}
            {status ? <p>{status}</p> : null}{pullError && <p role="alert">{pullError}</p>}
          </div>} />
      </div>
    </AppShell>
  );
}
