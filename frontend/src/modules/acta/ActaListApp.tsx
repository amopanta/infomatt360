import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchActaTemplates } from './api';
import type { ActaTemplateSummary } from './types';
import { useI18n } from '../../i18n';

export function ActaListApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<ActaTemplateSummary[]>([]);
  const [message, setMessage] = useState(t('acta.loadingTemplates'));

  useEffect(() => {
    fetchActaTemplates(projectId)
      .then((rows) => {
        setTemplates(rows);
        setMessage(rows.length ? '' : t('acta.noTemplatesYet'));
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  return (
    <AppShell title={t('acta.title')}>
      <main className="acta-shell">
        <header className="acta-list-header">
          <div>
            <h2>{t('acta.templateListTitle')}</h2>
            <p>{t('acta.templateListDescription')}</p>
          </div>
          <a className="primary" href="/acta/new">{t('acta.newTemplateLink')}</a>
        </header>
        {message ? <p role="status">{message}</p> : null}
        <div className="acta-template-grid">
          {templates.map((template) => (
            <a className="acta-template-card" key={template.id} href={`/acta/${template.id}`}>
              <strong>{template.name}</strong>
              <span>{template.layout_json ? t('acta.visualBuilder') : t('acta.legacyHtml')}</span>
            </a>
          ))}
        </div>
      </main>
    </AppShell>
  );
}
