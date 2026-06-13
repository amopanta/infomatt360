import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { fetchRuntimeTemplate, saveRuntimeRecord } from './api';
import { RuntimeRenderer } from './RuntimeRenderer';
import type { RuntimeFormValues, RuntimeTemplate } from './types';

function getTemplateIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const runtimeIndex = parts.indexOf('runtime');
  return runtimeIndex >= 0 && parts[runtimeIndex + 1] ? parts[runtimeIndex + 1] : '';
}

export function RuntimeApp() {
  const [template, setTemplate] = useState<RuntimeTemplate | null>(null);
  const [values, setValues] = useState<RuntimeFormValues>({});
  const [status, setStatus] = useState('Cargando formulario...');

  const templateId = getTemplateIdFromPath();
  const projectId = localStorage.getItem('infomatt360_project_id') ?? '';

  useEffect(() => {
    if (!templateId) {
      setStatus('Debe abrir una URL con formato /runtime/{template_id}.');
      return;
    }

    fetchRuntimeTemplate(templateId)
      .then((result) => {
        setTemplate(result);
        setStatus('');
      })
      .catch((error: Error) => setStatus(error.message));
  }, [templateId]);

  function updateValue(fieldName: string, value: string | number | boolean | null) {
    setValues((current) => ({ ...current, [fieldName]: value }));
  }

  async function save() {
    if (!template || !projectId) {
      setStatus('Falta project_id en localStorage o plantilla runtime.');
      return;
    }

    await saveRuntimeRecord({ projectId, templateId: template.template_id, values });
    setStatus('Respuesta guardada correctamente.');
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
      <RuntimeRenderer template={template} values={values} onValueChange={updateValue} />
      <div className="runtime-actions">
        <button onClick={save}>Guardar respuesta</button>
        {status ? <p>{status}</p> : null}
      </div>
    </AppShell>
  );
}
