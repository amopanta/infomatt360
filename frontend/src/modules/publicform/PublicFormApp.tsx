import { useEffect, useState } from 'react';

import type { RuntimeFormValue, RuntimeFormValues, RuntimeTemplate } from '../runtime/types';
import { resolveFormValues } from '../runtime/formLogic';
import { usePullData } from '../runtime/pullData';
import { fetchPublicForm, submitPublicForm } from './api';
import { PublicSurveyRenderer } from './PublicSurveyRenderer';
import { useI18n } from '../../i18n';

type Status = 'loading' | 'ready' | 'submitting' | 'success' | 'error';

function tokenFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  const index = parts.indexOf('public-form');
  return index >= 0 && parts[index + 1] ? decodeURIComponent(parts[index + 1]) : '';
}

export function PublicFormApp() {
  const { t } = useI18n();
  const [token] = useState(tokenFromPath);
  const [template, setTemplate] = useState<RuntimeTemplate | null>(null);
  const [values, setValues] = useState<RuntimeFormValues>({});
  const [status, setStatus] = useState<Status>('loading');
  const [message, setMessage] = useState('');
  const { pulls, error: pullError, ready: pullsReady } = usePullData(template, values, token);

  useEffect(() => {
    if (template) setValues((current) => resolveFormValues(template, current, pulls));
  }, [pulls, template]);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setMessage(t('publicForm.incompleteLinkCode'));
      return;
    }
    fetchPublicForm(token)
      .then((result) => {
        setTemplate(result);
        setValues(resolveFormValues(result, {}));
        setStatus('ready');
      })
      .catch((error: Error) => {
        setStatus('error');
        setMessage(error.message);
      });
  }, [token]);

  function updateValue(fieldName: string, value: RuntimeFormValue) {
    setValues((current) => template ? resolveFormValues(template, { ...current, [fieldName]: value }, pulls) : { ...current, [fieldName]: value });
  }

  async function submit() {
    setStatus('submitting');
    setMessage('');
    try {
      if (pullError || !pullsReady) throw new Error(pullError || t('publicForm.waitCsv'));
      await submitPublicForm(token, template ? resolveFormValues(template, values, pulls) : values);
      setStatus('success');
    } catch (error) {
      setStatus('ready');
      setMessage(error instanceof Error ? error.message : t('publicForm.submitFailed'));
    }
  }

  if (status === 'loading') {
    return (
      <div className="auth-page">
        <main className="runtime-shell"><p>{t('publicForm.loadingForm')}</p></main>
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
          <h1>{t('publicForm.thankYou')}</h1>
          <p>{t('publicForm.responseRecorded')}</p>
        </main>
      </div>
    );
  }

  if (!template) return null;

  return <PublicSurveyRenderer template={template} values={values} onValueChange={updateValue} onSubmit={() => void submit()} submitting={status === 'submitting'} serverMessage={message} />;
}
