import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { createPublicLink, fetchPublicLinks, revokePublicLink } from './publicLinksApi';
import type { PublicFormLink, PublicFormLinkIssued } from './publicLinksApi';

function publicFormUrl(token: string): string {
  return `${window.location.origin}/public-form/${token}`;
}

export function PublicLinksApp() {
  const { t } = useI18n();
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
        const requested = new URLSearchParams(window.location.search).get('template');
        if (rows.length) setTemplateId(rows.find((row) => row.id === requested)?.id ?? rows[0].id);
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  async function loadLinks(id: string) {
    if (!id) return;
    try {
      setLinks(await fetchPublicLinks(id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.publicLinks.queryError'));
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
      setMessage(error instanceof Error ? error.message : t('admin.publicLinks.createError'));
    } finally {
      setCreating(false);
    }
  }

  async function submitRevoke(linkId: string) {
    try {
      await revokePublicLink(linkId);
      setMessage(t('admin.publicLinks.linkRevoked'));
      await loadLinks(templateId);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.publicLinks.revokeError'));
    }
  }

  function linkStatus(link: PublicFormLink): { label: string; className: string } {
    if (link.revoked_at) return { label: t('admin.publicLinks.statusRevoked'), className: 'failed' };
    if (link.expires_at && new Date(link.expires_at).getTime() <= Date.now()) return { label: t('admin.publicLinks.statusExpired'), className: 'failed' };
    if (link.max_submissions !== null && link.max_submissions !== undefined && link.submission_count >= link.max_submissions) return { label: t('admin.publicLinks.statusExhausted'), className: 'skipped' };
    return { label: t('admin.publicLinks.statusActive'), className: 'sent' };
  }

  return (
    <AppShell title={t('admin.publicLinks.title')}>
      <main className="audit-shell">
        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.publicLinks.generateTitle')}</h2>
              <p>{t('admin.publicLinks.generateDescription')}</p>
            </div>
          </header>
          {message ? <p role="status" className="erp-message">{message}</p> : null}
          <div className="ai-analyze-inline">
            <label>{t('admin.publicLinks.formLabel')}
              <select value={templateId} onChange={(event) => setTemplateId(event.target.value)}>
                {templates.map((template) => <option key={template.id} value={template.id}>{template.name} ({template.status})</option>)}
              </select>
            </label>
            <label>{t('admin.publicLinks.labelOptional')}<input value={label} onChange={(event) => setLabel(event.target.value)} placeholder={t('admin.publicLinks.labelPlaceholder')} /></label>
            <label>{t('admin.publicLinks.maxSubmissions')}<input type="number" min={1} value={maxSubmissions} onChange={(event) => setMaxSubmissions(event.target.value)} /></label>
            <label>{t('admin.publicLinks.expiresInHours')}<input type="number" min={1} value={expiresInHours} onChange={(event) => setExpiresInHours(event.target.value)} /></label>
            <button className="primary" disabled={creating || !templateId} onClick={() => void submitCreate()}>
              {creating ? t('admin.publicLinks.generating') : t('admin.publicLinks.generateLink')}
            </button>
          </div>
          {issued ? (
            <article className="ds-map-card">
              <strong>{t('admin.publicLinks.linkGenerated')}</strong>
              <span>{publicFormUrl(issued.token)}</span>
            </article>
          ) : null}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.publicLinks.linksTitle')}</h2>
            </div>
          </header>
          {!links.length ? <p>{t('admin.publicLinks.noLinks')}</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('admin.publicLinks.labelColumn')}</th>
                  <th>{t('admin.publicLinks.responsesColumn')}</th>
                  <th>{t('admin.publicLinks.expiresColumn')}</th>
                  <th>{t('admin.publicLinks.statusColumn')}</th>
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
                      <td>{link.expires_at ? new Date(link.expires_at).toLocaleString() : t('admin.publicLinks.noExpiry')}</td>
                      <td><span className={`wa-status ${state.className}`}>{state.label}</span></td>
                      <td>{!link.revoked_at ? <button onClick={() => void submitRevoke(link.id)}>{t('admin.publicLinks.revoke')}</button> : null}</td>
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
