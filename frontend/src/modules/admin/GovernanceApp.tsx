import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY, currentProjectPermissions } from '../auth/session';
import {
  createSupportTicket,
  fetchEmergencyKeys,
  fetchSupportTickets,
  issueEmergencyKey,
  resolveSupportTicket,
  revokeEmergencyKey,
  runTenantClean,
} from './governanceApi';
import type { EmergencyAccessKey, EmergencyAccessKeyIssued, SupportTicket, TenantCleanResult } from './governanceApi';

type Tab = 'tenant-clean' | 'emergency-access' | 'support';

const TENANT_CLEAN_PERMISSION = 'organizations.tenant_clean';
const EMERGENCY_ACCESS_PERMISSION = 'identity.users.manage';
const SUPPORT_PERMISSION = 'support.tickets.manage';

export function GovernanceApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const permissions = currentProjectPermissions();
  const canTenantClean = permissions.has(TENANT_CLEAN_PERMISSION);
  const canEmergencyAccess = permissions.has(EMERGENCY_ACCESS_PERMISSION);
  const canSupport = permissions.has(SUPPORT_PERMISSION);

  const firstAvailableTab: Tab = canTenantClean ? 'tenant-clean' : canEmergencyAccess ? 'emergency-access' : 'support';
  const [tab, setTab] = useState<Tab>(firstAvailableTab);
  const [message, setMessage] = useState('');

  // Tenant clean
  const [organizationId, setOrganizationId] = useState('');
  const [confirmSlug, setConfirmSlug] = useState('');
  const [totpCode, setTotpCode] = useState('');
  const [tenantCleanResult, setTenantCleanResult] = useState<TenantCleanResult | null>(null);

  // Emergency access
  const [emergencyUserId, setEmergencyUserId] = useState('');
  const [emergencyHours, setEmergencyHours] = useState(24);
  const [emergencyPurpose, setEmergencyPurpose] = useState('');
  const [issuedKey, setIssuedKey] = useState<EmergencyAccessKeyIssued | null>(null);
  const [emergencyKeys, setEmergencyKeys] = useState<EmergencyAccessKey[]>([]);

  // Support
  const [ticketSubject, setTicketSubject] = useState('');
  const [ticketDescription, setTicketDescription] = useState('');
  const [ticketStatusFilter, setTicketStatusFilter] = useState('');
  const [tickets, setTickets] = useState<SupportTicket[]>([]);

  function ticketStatusLabel(status: string) {
    const labels: Record<string, string> = {
      open: t('admin.governance.ticketStatusOpen'),
      auto_resolved: t('admin.governance.ticketStatusAutoResolved'),
      resolved: t('admin.governance.ticketStatusResolved'),
    };
    return labels[status] ?? status;
  }

  function ticketStatusClass(status: string) {
    if (status === 'auto_resolved') return 'sent';
    if (status === 'resolved') return 'sent';
    return 'skipped';
  }

  async function loadEmergencyKeys() {
    if (!projectId) return;
    try {
      setEmergencyKeys(await fetchEmergencyKeys(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorLoadKeys'));
    }
  }

  async function loadTickets() {
    if (!projectId) return;
    try {
      setTickets(await fetchSupportTickets(projectId, ticketStatusFilter || undefined));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorLoadTickets'));
    }
  }

  useEffect(() => { if (canEmergencyAccess) void loadEmergencyKeys(); }, [projectId, canEmergencyAccess]);
  useEffect(() => { if (canSupport) void loadTickets(); }, [projectId, canSupport, ticketStatusFilter]);

  async function submitTenantClean() {
    const confirmed = window.confirm(
      t('admin.governance.confirmPurge', { org: organizationId }),
    );
    if (!confirmed) return;
    try {
      const result = await runTenantClean({ organizationId: organizationId.trim(), confirmSlug: confirmSlug.trim(), totpCode: totpCode.trim() });
      setTenantCleanResult(result);
      setMessage(t('admin.governance.purgeCompleted', { count: result.projects_purged.length }));
      setTotpCode('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorRunPurge'));
    }
  }

  async function submitIssueKey() {
    try {
      const issued = await issueEmergencyKey({ projectId, userId: emergencyUserId.trim(), hoursValid: emergencyHours, purpose: emergencyPurpose.trim() });
      setIssuedKey(issued);
      setEmergencyUserId('');
      setEmergencyPurpose('');
      await loadEmergencyKeys();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorIssueKey'));
    }
  }

  async function submitRevokeKey(keyId: string) {
    try {
      await revokeEmergencyKey(keyId);
      setMessage(t('admin.governance.keyRevoked'));
      await loadEmergencyKeys();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorRevokeKey'));
    }
  }

  async function submitTicket() {
    try {
      const ticket = await createSupportTicket({ projectId, subject: ticketSubject.trim(), description: ticketDescription.trim() });
      setMessage(
        ticket.status === 'auto_resolved'
          ? t('admin.governance.ticketAutoResolved', { response: ticket.auto_response_text })
          : t('admin.governance.ticketEscalated'),
      );
      setTicketSubject('');
      setTicketDescription('');
      await loadTickets();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorCreateTicket'));
    }
  }

  async function submitResolveTicket(ticketId: string) {
    try {
      await resolveSupportTicket(ticketId);
      setMessage(t('admin.governance.ticketResolved'));
      await loadTickets();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.governance.errorResolveTicket'));
    }
  }

  return (
    <AppShell title={t('admin.governance.title')}>
      <main className="audit-shell">
        <nav className="erp-tabs">
          {canTenantClean ? <button className={tab === 'tenant-clean' ? 'active' : undefined} onClick={() => setTab('tenant-clean')}>{t('admin.governance.tabTenantClean')}</button> : null}
          {canEmergencyAccess ? <button className={tab === 'emergency-access' ? 'active' : undefined} onClick={() => setTab('emergency-access')}>{t('admin.governance.tabEmergencyAccess')}</button> : null}
          {canSupport ? <button className={tab === 'support' ? 'active' : undefined} onClick={() => setTab('support')}>{t('admin.governance.tabSupport')}</button> : null}
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'tenant-clean' && canTenantClean ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>{t('admin.governance.tenantCleanTitle')}</h2>
                <p>{t('admin.governance.tenantCleanDescription')}</p>
              </div>
            </header>
            <div className="ai-analyze-inline">
              <label>{t('admin.governance.organizationIdLabel')}<input value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} placeholder={t('admin.governance.organizationIdPlaceholder')} /></label>
              <label>{t('admin.governance.confirmSlugLabel')}<input value={confirmSlug} onChange={(event) => setConfirmSlug(event.target.value)} placeholder={t('admin.governance.confirmSlugPlaceholder')} /></label>
              <label>{t('admin.governance.totpLabel')}<input value={totpCode} onChange={(event) => setTotpCode(event.target.value)} placeholder={t('admin.governance.totpPlaceholder')} maxLength={6} /></label>
              <button
                className="danger"
                disabled={!organizationId.trim() || !confirmSlug.trim() || totpCode.trim().length !== 6}
                onClick={() => void submitTenantClean()}
              >
                {t('admin.governance.executePurge')}
              </button>
            </div>
            {tenantCleanResult ? (
              <article className="ds-map-card">
                <strong>{t('admin.governance.purgedProjects', { projects: tenantCleanResult.projects_purged.join(', ') || t('admin.governance.purgedNone') })}</strong>
                <ul>
                  {Object.entries(tenantCleanResult.deleted_counts).map(([table, count]) => (
                    <li key={table}>{table}: {count}</li>
                  ))}
                </ul>
              </article>
            ) : null}
          </section>
        ) : null}

        {tab === 'emergency-access' && canEmergencyAccess ? (
          <section className="ds-maps">
            <div className="ds-map-create">
              <h2>{t('admin.governance.issueKeyTitle')}</h2>
              <p>{t('admin.governance.issueKeyDescription')}</p>
              <label>{t('admin.governance.userIdLabel')}<input value={emergencyUserId} onChange={(event) => setEmergencyUserId(event.target.value)} placeholder={t('admin.governance.userIdPlaceholder')} /></label>
              <label>{t('admin.governance.hoursLabel')}<input type="number" min={1} max={168} value={emergencyHours} onChange={(event) => setEmergencyHours(Number(event.target.value))} /></label>
              <label>{t('admin.governance.purposeLabel')}<input value={emergencyPurpose} onChange={(event) => setEmergencyPurpose(event.target.value)} placeholder={t('admin.governance.purposePlaceholder')} /></label>
              <button className="primary" disabled={!emergencyUserId.trim()} onClick={() => void submitIssueKey()}>{t('admin.governance.issueButton')}</button>
              {issuedKey ? (
                <article className="ds-map-card">
                  <strong>{t('admin.governance.codeShownOnce', { code: issuedKey.code })}</strong>
                  <span>{t('admin.governance.expiresAt', { date: new Date(issuedKey.expires_at).toLocaleString() })}</span>
                </article>
              ) : null}
            </div>
            <div className="ds-map-list">
              <h2>{t('admin.governance.projectKeys')}</h2>
              {!emergencyKeys.length ? <p>{t('admin.governance.noKeysYet')}</p> : null}
              {emergencyKeys.map((key) => (
                <article key={key.id} className="ds-map-card">
                  <strong>{t('admin.governance.userPrefix', { id: key.user_id })}</strong>
                  <span>{key.purpose || t('admin.governance.noPurpose')}</span>
                  <small>
                    {t('admin.governance.expiresPrefix', { date: new Date(key.expires_at).toLocaleString() })}
                    {key.used_at ? ` · ${t('admin.governance.usedPrefix', { date: new Date(key.used_at).toLocaleString() })}` : ''}
                    {key.revoked_at ? ` · ${t('admin.governance.revokedPrefix', { date: new Date(key.revoked_at).toLocaleString() })}` : ''}
                  </small>
                  {!key.used_at && !key.revoked_at ? <button onClick={() => void submitRevokeKey(key.id)}>{t('admin.governance.revokeButton')}</button> : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {tab === 'support' && canSupport ? (
          <section className="ds-maps">
            <div className="ds-map-create">
              <h2>{t('admin.governance.reportTitle')}</h2>
              <label>{t('admin.governance.subjectLabel')}<input value={ticketSubject} onChange={(event) => setTicketSubject(event.target.value)} placeholder={t('admin.governance.subjectPlaceholder')} /></label>
              <label>{t('admin.governance.descriptionLabel')}<textarea rows={3} value={ticketDescription} onChange={(event) => setTicketDescription(event.target.value)} /></label>
              <button className="primary" disabled={!ticketSubject.trim() || !ticketDescription.trim()} onClick={() => void submitTicket()}>{t('admin.governance.reportButton')}</button>
            </div>
            <div className="ds-map-list">
              <header>
                <h2>{t('admin.governance.projectTickets')}</h2>
                <select value={ticketStatusFilter} onChange={(event) => setTicketStatusFilter(event.target.value)}>
                  <option value="">{t('admin.governance.allStatuses')}</option>
                  <option value="open">{t('admin.governance.ticketStatusOpen')}</option>
                  <option value="auto_resolved">{t('admin.governance.ticketStatusAutoResolved')}</option>
                  <option value="resolved">{t('admin.governance.ticketStatusResolved')}</option>
                </select>
              </header>
              {!tickets.length ? <p>{t('admin.governance.noTicketsYet')}</p> : null}
              {tickets.map((ticket) => (
                <article key={ticket.id} className="ds-map-card">
                  <strong>{ticket.subject}</strong>
                  <span className={`wa-status ${ticketStatusClass(ticket.status)}`}>{ticketStatusLabel(ticket.status)}</span>
                  <p>{ticket.description}</p>
                  {ticket.auto_response_text ? <small>{t('admin.governance.autoResponse', { text: ticket.auto_response_text })}</small> : null}
                  <small>{new Date(ticket.created_at).toLocaleString()}</small>
                  {ticket.status === 'open' ? <button onClick={() => void submitResolveTicket(ticket.id)}>{t('admin.governance.markResolved')}</button> : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
