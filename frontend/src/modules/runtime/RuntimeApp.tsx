import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { enqueueRecord } from '../offline/offlineSync';
import { fetchCaptureParticipants, fetchRuntimeTemplate, saveRuntimeRecord, toRuntimeValueList } from './api';
import type { EligibleParticipant } from './api';
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
  const [participantsReady, setParticipantsReady] = useState(false);
  const [participantRequired, setParticipantRequired] = useState(false);
  const [participantQuery, setParticipantQuery] = useState('');

  const templateId = getTemplateIdFromPath();
  const isPreview = new URLSearchParams(window.location.search).get('preview') === '1';
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const participantStorageKey = `infomatt360_participant_${templateId}`;
  const [participantId, setParticipantId] = useState(() => localStorage.getItem(participantStorageKey) || new URLSearchParams(window.location.search).get('participantId') || '');
  const { values, setValues, clearDraft } = useRuntimeDraft(`${templateId || 'sin-template'}${isPreview ? '-vista-previa' : ''}`);
  const { pulls, error: pullError, ready: pullsReady } = usePullData(template, values);

  useEffect(() => {
    if (!templateId || isPreview) return;
    fetchCaptureParticipants(templateId)
      .then(({ participants: rows, required }) => { setParticipants(rows); setParticipantRequired(required); setParticipantsReady(true); })
      .catch((error: Error) => { setParticipantsReady(false); setStatus(error.message); });
  }, [templateId, isPreview]);

  useEffect(() => {
    if (participantId) localStorage.setItem(participantStorageKey, participantId);
    else localStorage.removeItem(participantStorageKey);
  }, [participantId, participantStorageKey]);

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

  async function save() {
    if (!template || !projectId) {
      setStatus('Falta proyecto activo en la sesion o plantilla runtime.');
      return;
    }

    try {
      if (!participantsReady) { setStatus('Espera a que se carguen los participantes asociados.'); return; }
      if (participantRequired && !participantId) { setStatus('Selecciona el participante antes de guardar esta respuesta.'); return; }
      if (participantId && !participants.some((person) => person.id === participantId)) { setStatus('El participante seleccionado ya no está habilitado para este formulario. Selecciona otro.'); return; }
      if (pullError || !pullsReady) { setStatus(pullError || 'Espera a que termine la consulta del CSV.'); return; }
      const resolved = resolveFormValues(template, values, pulls);
      const invalid = validateFormValues(template, resolved);
      if (invalid) { setStatus(invalid); return; }
      await saveRuntimeRecord({ projectId, templateId: template.template_id, participantId: participantId || null, values: resolved });
      clearDraft();
      setParticipantId('');
      setParticipantQuery('');
      setStatus('Respuesta guardada y asociada correctamente.');
    } catch (error) {
      // TypeError = fetch no pudo conectarse (sin red); un error HTTP real
      // (validacion, permisos, etc.) no se debe encolar porque volveria a
      // fallar igual al sincronizar.
      if (error instanceof TypeError) {
        if (participantId) { setStatus('Sin conexión: conserva el formulario abierto. Para mantener la asociación con el participante, guarda la respuesta cuando vuelva la red.'); return; }
        await enqueueRecord({ projectId, templateId: template.template_id, values: toRuntimeValueList(resolveFormValues(template, values, pulls)) });
        clearDraft();
        setStatus('Sin conexion: la respuesta quedo guardada localmente. Sincronizala desde el boton de la barra superior cuando vuelva la red.');
        return;
      }
      setStatus(error instanceof Error ? error.message : 'No fue posible guardar la respuesta.');
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
        {!isPreview && <section className="runtime-participant-picker" aria-label="Asociar participante a esta respuesta"><h2>¿A quién corresponde esta respuesta?</h2><p>Busca por nombre, documento o código. La respuesta aparecerá en el historial de la persona seleccionada.</p><input type="search" aria-label="Buscar participante" placeholder="Buscar participante" value={participantQuery} onChange={(event) => setParticipantQuery(event.target.value)} /><select aria-label="Participante de la respuesta" value={participantId} disabled={!participantsReady} onChange={(event) => setParticipantId(event.target.value)}><option value="">{participantRequired ? 'Selecciona un participante' : 'Sin participante (opcional)'}</option>{participants.filter((person) => !participantQuery.trim() || `${person.full_name} ${person.document_id || ''} ${person.external_code || ''} ${person.municipality || ''}`.toLocaleLowerCase().includes(participantQuery.trim().toLocaleLowerCase()) || person.id === participantId).slice(0, 100).map((person) => <option key={person.id} value={person.id}>{person.full_name} · {person.document_id || person.external_code || person.municipality || 'Sin identificador'}</option>)}</select><small>{participantsReady ? `${participants.length} participante(s) habilitado(s) para este formulario.${participantRequired ? ' Selección obligatoria.' : ''}` : 'Cargando participantes...'}</small>{participantsReady && participantRequired && participants.length === 0 && <p role="alert">No hay participantes habilitados. Revisa la fuente configurada para este formulario.</p>}{participantId && <strong>La respuesta quedará asociada a {participants.find((person) => person.id === participantId)?.full_name || 'este participante'}.</strong>}</section>}
        <RuntimeRenderer template={template} projectId={projectId} values={values} onValueChange={updateValue} />
        <div className="runtime-actions">
          {!isPreview && <button onClick={save}>Guardar respuesta</button>}
          {status ? <p>{status}</p> : null}{pullError && <p role="alert">{pullError}</p>}
        </div>
      </div>
    </AppShell>
  );
}
