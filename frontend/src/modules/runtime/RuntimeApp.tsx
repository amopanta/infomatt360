import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchRuntimeTemplate, saveRuntimeRecord } from './api';
import { RuntimeRenderer, themeStyle } from './RuntimeRenderer';
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

  const templateId = getTemplateIdFromPath();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const { values, setValues, clearDraft } = useRuntimeDraft(templateId || 'sin-template');

  useEffect(() => {
    if (!templateId) {
      setStatus('Debe abrir una URL con formato /runtime/{template_id}.');
      return;
    }

    fetchRuntimeTemplate(templateId)
      .then((result) => {
        setTemplate(result);
        setStatus('Borrador local activo.');
      })
      .catch((error: Error) => setStatus(error.message));
  }, [templateId]);

  function updateValue(fieldName: string, value: RuntimeFormValue) {
    setValues((current) => ({ ...current, [fieldName]: value }));
  }

  async function save() {
    if (!template || !projectId) {
      setStatus('Falta proyecto activo en la sesion o plantilla runtime.');
      return;
    }

    await saveRuntimeRecord({ projectId, templateId: template.template_id, values });
    clearDraft();
    setStatus('Respuesta guardada correctamente. Borrador local limpiado.');
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
        <RuntimeRenderer template={template} projectId={projectId} values={values} onValueChange={updateValue} />
        <div className="runtime-actions">
          <button onClick={save}>Guardar respuesta</button>
          {status ? <p>{status}</p> : null}
        </div>
      </div>
    </AppShell>
  );
}
