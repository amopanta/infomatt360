import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { createPublicLink, fetchPublicLinks, revokePublicLink } from './publicLinksApi';
import type { PublicFormLink, PublicFormLinkIssued } from './publicLinksApi';

function publicFormUrl(token: string): string {
  return `${window.location.origin}/public-form/${token}`;
}

export function PublicLinksApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [templateId, setTemplateId] = useState('');
  const [label, setLabel] = useState('');
  const [maxSubmissions, setMaxSubmissions] = useState('');
  const [expiresInHours, setExpiresInHours] = useState('');
  const [links, setLinks] = useState<PublicFormLink[]>([]);
  const [issued, setIssued] = useState<PublicFormLinkIssued | null>(null);
  const [message, setMessage] = useState('');
  const [creating, setCreating] = useState(false);

  useEffect(() => {
    fetchProjectTemplates(projectId)
      .then((rows) => {
        setTemplates(rows);
        if (rows.length) setTemplateId(rows[0].id);
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  async function loadLinks(id: string) {
    if (!id) return;
    try {
      setLinks(await fetchPublicLinks(id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar los enlaces publicos.');
    }
  }

  useEffect(() => { void loadLinks(templateId); }, [templateId]);

  async function submitCreate() {
    if (!templateId) return;
    setCreating(true);
    try {
      const link = await createPublicLink({
        templateId,
        label: label.trim() || undefined,
        maxSubmissions: maxSubmissions ? Number(maxSubmissions) : undefined,
        expiresInHours: expiresInHours ? Number(expiresInHours) : undefined,
      });
      setIssued(link);
      setLabel('');
      setMaxSubmissions('');
      setExpiresInHours('');
      await loadLinks(templateId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible generar el enlace publico.');
    } finally {
      setCreating(false);
    }
  }

  async function submitRevoke(linkId: string) {
    try {
      await revokePublicLink(linkId);
      setMessage('Enlace revocado.');
      await loadLinks(templateId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible revocar el enlace.');
    }
  }

  function linkStatus(link: PublicFormLink): { label: string; className: string } {
    if (link.revoked_at) return { label: 'Revocado', className: 'failed' };
    if (link.expires_at && new Date(link.expires_at).getTime() <= Date.now()) return { label: 'Vencido', className: 'failed' };
    if (link.max_submissions !== null && link.max_submissions !== undefined && link.submission_count >= link.max_submissions) return { label: 'Agotado', className: 'skipped' };
    return { label: 'Activo', className: 'sent' };
  }

  return (
    <AppShell title="Formularios abiertos (captura pública)">
      <main className="audit-shell">
        <section className="audit-panel">
          <header>
            <div>
              <h2>Generar enlace público</h2>
              <p>Cualquier persona con el enlace puede responder el formulario sin cuenta, similar a una encuesta de LimeSurvey (ver docs/92).</p>
            </div>
          </header>
          {message ? <p role="status" className="erp-message">{message}</p> : null}
          <div className="ai-analyze-inline">
            <label>Formulario
              <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
                {templates.map((template) => <option key={template.id} value={template.id}>{template.name} ({template.status})</option>)}
              </select>
            </label>
            <label>Etiqueta (opcional)<input value={label} onChange={(event) => setLabel(event.target.value)} placeholder="Feria comercial Bogotá" /></label>
            <label>Máximo de respuestas (vacío = ilimitado)<input type="number" min={1} value={maxSubmissions} onChange={(event) => setMaxSubmissions(event.target.value)} /></label>
            <label>Vence en horas (vacío = sin vencimiento)<input type="number" min={1} value={expiresInHours} onChange={(event) => setExpiresInHours(event.target.value)} /></label>
            <button className="primary" disabled={creating || !templateId} onClick={() => void submitCreate()}>
              {creating ? 'Generando…' : 'Generar enlace'}
            </button>
          </div>
          {issued ? (
            <article className="ds-map-card">
              <strong>Enlace generado (se muestra una sola vez el token completo):</strong>
              <span>{publicFormUrl(issued.token)}</span>
            </article>
          ) : null}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>Enlaces del formulario seleccionado</h2>
            </div>
          </header>
          {!links.length ? <p>Este formulario aún no tiene enlaces públicos.</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Etiqueta</th>
                  <th>Respuestas</th>
                  <th>Vence</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {links.map((link) => {
                  const state = linkStatus(link);
                  return (
                    <tr key={link.id}>
                      <td>{link.label || '—'}</td>
                      <td>{link.submission_count}{link.max_submissions ? ` / ${link.max_submissions}` : ''}</td>
                      <td>{link.expires_at ? new Date(link.expires_at).toLocaleString() : 'Sin vencimiento'}</td>
                      <td><span className={`wa-status ${state.className}`}>{state.label}</span></td>
                      <td>{!link.revoked_at ? <button onClick={() => void submitRevoke(link.id)}>Revocar</button> : null}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
