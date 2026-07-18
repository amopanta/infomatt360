import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchActaTemplates } from './api';
import type { ActaTemplateSummary } from './types';

export function ActaListApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<ActaTemplateSummary[]>([]);
  const [message, setMessage] = useState('Cargando plantillas de acta...');

  useEffect(() => {
    fetchActaTemplates(projectId)
      .then((rows) => {
        setTemplates(rows);
        setMessage(rows.length ? '' : 'Este proyecto aún no tiene plantillas de acta.');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  return (
    <AppShell title="Actas">
      <main className="acta-shell">
        <header className="acta-list-header">
          <div>
            <h2>Plantillas de acta</h2>
            <p>Constructor visual: logo, encabezado, tabla de datos y firma, generados a partir de un registro real.</p>
          </div>
          <a className="primary" href="/acta/new">Nueva plantilla de acta</a>
        </header>
        {message ? <p role="status">{message}</p> : null}
        <div className="acta-template-grid">
          {templates.map((template) => (
            <a className="acta-template-card" key={template.id} href={`/acta/${template.id}`}>
              <strong>{template.name}</strong>
              <span>{template.layout_json ? 'Constructor visual' : 'Plantilla HTML (legado)'}</span>
            </a>
          ))}
        </div>
      </main>
    </AppShell>
  );
}
