import { useEffect, useState } from 'react';

import { RuntimeRenderer, themeStyle } from '../runtime/RuntimeRenderer';
import type { RuntimeFormValue, RuntimeFormValues, RuntimeTemplate } from '../runtime/types';
import { fetchPublicForm, submitPublicForm } from './api';

type Status = 'loading' | 'ready' | 'submitting' | 'success' | 'error';

function tokenFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const index = parts.indexOf('public-form');
  return index >= 0 && parts[index + 1] ? decodeURIComponent(parts[index + 1]) : '';
}

export function PublicFormApp() {
  const [token] = useState(tokenFromPath);
  const [template, setTemplate] = useState<RuntimeTemplate | null>(null);
  const [values, setValues] = useState<RuntimeFormValues>({});
  const [status, setStatus] = useState<Status>('loading');
  const [message, setMessage] = useState('');

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage('Este enlace esta incompleto: falta el codigo de acceso.');
      return;
    }
    fetchPublicForm(token)
      .then((result) => {
        setTemplate(result);
        setStatus('ready');
      })
      .catch((error: Error) => {
        setStatus('error');
        setMessage(error.message);
      });
  }, [token]);

  function updateValue(fieldName: string, value: RuntimeFormValue) {
    setValues((current) => ({ ...current, [fieldName]: value }));
  }

  async function submit() {
    setStatus('submitting');
    setMessage('');
    try {
      await submitPublicForm(token, values);
      setStatus('success');
    } catch (error) {
      setStatus('ready');
      setMessage(error instanceof Error ? error.message : 'No fue posible enviar la respuesta.');
    }
  }

  if (status === 'loading') {
    return (
      <div className="auth-page">
        <main className="runtime-shell"><p>Cargando formulario...</p></main>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="auth-page">
        <main className="runtime-shell">
          <p role="alert">{message}</p>
        </main>
      </div>
    );
  }

  if (status === 'success') {
    return (
      <div className="auth-page">
        <main className="runtime-shell public-form-success">
          <h1>¡Gracias!</h1>
          <p>Tu respuesta fue registrada correctamente.</p>
        </main>
      </div>
    );
  }

  if (!template) return null;

  return (
    <div className="auth-page">
      <div className="runtime-shell" style={themeStyle(template.theme_json)}>
        <RuntimeRenderer template={template} projectId="" values={values} onValueChange={updateValue} uploadsDisabled />
        <div className="runtime-page-actions public-form-actions">
          <button disabled={status === 'submitting'} onClick={() => void submit()}>
            {status === 'submitting' ? 'Enviando…' : 'Enviar respuesta'}
          </button>
          {message ? <p role="alert">{message}</p> : null}
        </div>
      </div>
    </div>
  );
}
