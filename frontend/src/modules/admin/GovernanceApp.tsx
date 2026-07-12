import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
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

function ticketStatusLabel(status: string) {
  const labels: Record<string, string> = { open: 'Abierto', auto_resolved: 'Auto-resuelto', resolved: 'Resuelto' };
  return labels[status] ?? status;
}

function ticketStatusClass(status: string) {
  if (status === 'auto_resolved') return 'sent';
  if (status === 'resolved') return 'sent';
  return 'skipped';
}

export function GovernanceApp() {
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

  async function loadEmergencyKeys() {
    if (!projectId) return;
    try {
      setEmergencyKeys(await fetchEmergencyKeys(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar las credenciales de emergencia.');
    }
  }

  async function loadTickets() {
    if (!projectId) return;
    try {
      setTickets(await fetchSupportTickets(projectId, ticketStatusFilter || undefined));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar los tickets de soporte.');
    }
  }

  useEffect(() => { if (canEmergencyAccess) void loadEmergencyKeys(); }, [projectId, canEmergencyAccess]);
  useEffect(() => { if (canSupport) void loadTickets(); }, [projectId, canSupport, ticketStatusFilter]);

  async function submitTenantClean() {
    const confirmed = window.confirm(
      `Vas a purgar TODOS los datos de prueba (participantes, registros, evidencias, etc.) de la organizacion "${organizationId}". ` +
      'Esta accion es irreversible. ¿Confirmas que quieres continuar?',
    );
    if (!confirmed) return;
    try {
      const result = await runTenantClean({ organizationId: organizationId.trim(), confirmSlug: confirmSlug.trim(), totpCode: totpCode.trim() });
      setTenantCleanResult(result);
      setMessage(`Purga completada: ${result.projects_purged.length} proyecto(s) afectado(s).`);
      setTotpCode('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible ejecutar la purga.');
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
      setMessage(error instanceof Error ? error.message : 'No fue posible emitir la credencial.');
    }
  }

  async function submitRevokeKey(keyId: string) {
    try {
      await revokeEmergencyKey(keyId);
      setMessage('Credencial revocada.');
      await loadEmergencyKeys();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible revocar la credencial.');
    }
  }

  async function submitTicket() {
    try {
      const ticket = await createSupportTicket({ projectId, subject: ticketSubject.trim(), description: ticketDescription.trim() });
      setMessage(
        ticket.status === 'auto_resolved'
          ? `Ticket auto-resuelto: ${ticket.auto_response_text}`
          : 'Ticket registrado; se escalo a soporte humano.',
      );
      setTicketSubject('');
      setTicketDescription('');
      await loadTickets();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible reportar el ticket.');
    }
  }

  async function submitResolveTicket(ticketId: string) {
    try {
      await resolveSupportTicket(ticketId);
      setMessage('Ticket marcado como resuelto.');
      await loadTickets();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible resolver el ticket.');
    }
  }

  return (
    <AppShell title="Gobernanza y soporte">
      <main className="audit-shell">
        <nav className="erp-tabs">
          {canTenantClean ? <button className={tab === 'tenant-clean' ? 'active' : undefined} onClick={() => setTab('tenant-clean')}>Purga de organización</button> : null}
          {canEmergencyAccess ? <button className={tab === 'emergency-access' ? 'active' : undefined} onClick={() => setTab('emergency-access')}>Credenciales de emergencia</button> : null}
          {canSupport ? <button className={tab === 'support' ? 'active' : undefined} onClick={() => setTab('support')}>Mesa de ayuda</button> : null}
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'tenant-clean' && canTenantClean ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>Purga controlada de entorno (Tenant Clean)</h2>
                <p>Accion critica: borra datos de prueba/operativos de todos los proyectos de la organizacion. Protege usuarios, identidad, inventario ERP y configuracion (ver docs/90).</p>
              </div>
            </header>
            <div className="ai-analyze-inline">
              <label>ID de la organización<input value={organizationId} onChange={(event) => setOrganizationId(event.target.value)} placeholder="organization_id" /></label>
              <label>Slug de confirmación<input value={confirmSlug} onChange={(event) => setConfirmSlug(event.target.value)} placeholder="slug exacto de la organización" /></label>
              <label>Código 2FA<input value={totpCode} onChange={(event) => setTotpCode(event.target.value)} placeholder="123456" maxLength={6} /></label>
              <button
                className="danger"
                disabled={!organizationId.trim() || !confirmSlug.trim() || totpCode.trim().length !== 6}
                onClick={() => void submitTenantClean()}
              >
                Ejecutar purga
              </button>
            </div>
            {tenantCleanResult ? (
              <article className="ds-map-card">
                <strong>Proyectos purgados: {tenantCleanResult.projects_purged.join(', ') || 'ninguno'}</strong>
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
              <h2>Emitir credencial de emergencia</h2>
              <p>Codigo de un solo uso, valido por horas, para auditores externos o gestores bloqueados (ver docs/91).</p>
              <label>ID del usuario<input value={emergencyUserId} onChange={(event) => setEmergencyUserId(event.target.value)} placeholder="user_id" /></label>
              <label>Horas de vigencia<input type="number" min={1} max={168} value={emergencyHours} onChange={(event) => setEmergencyHours(Number(event.target.value))} /></label>
              <label>Propósito (opcional)<input value={emergencyPurpose} onChange={(event) => setEmergencyPurpose(event.target.value)} placeholder="auditor externo, gestor bloqueado, etc." /></label>
              <button className="primary" disabled={!emergencyUserId.trim()} onClick={() => void submitIssueKey()}>Emitir</button>
              {issuedKey ? (
                <article className="ds-map-card">
                  <strong>Código (se muestra una sola vez): {issuedKey.code}</strong>
                  <span>Vence: {new Date(issuedKey.expires_at).toLocaleString()}</span>
                </article>
              ) : null}
            </div>
            <div className="ds-map-list">
              <h2>Credenciales del proyecto</h2>
              {!emergencyKeys.length ? <p>Sin credenciales de emergencia emitidas.</p> : null}
              {emergencyKeys.map((key) => (
                <article key={key.id} className="ds-map-card">
                  <strong>Usuario: {key.user_id}</strong>
                  <span>{key.purpose || 'Sin proposito indicado'}</span>
                  <small>
                    Vence {new Date(key.expires_at).toLocaleString()}
                    {key.used_at ? ` · usada ${new Date(key.used_at).toLocaleString()}` : ''}
                    {key.revoked_at ? ` · revocada ${new Date(key.revoked_at).toLocaleString()}` : ''}
                  </small>
                  {!key.used_at && !key.revoked_at ? <button onClick={() => void submitRevokeKey(key.id)}>Revocar</button> : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}

        {tab === 'support' && canSupport ? (
          <section className="ds-maps">
            <div className="ds-map-create">
              <h2>Reportar falla técnica</h2>
              <label>Asunto<input value={ticketSubject} onChange={(event) => setTicketSubject(event.target.value)} placeholder="Falla sincronizacion" /></label>
              <label>Descripción<textarea rows={3} value={ticketDescription} onChange={(event) => setTicketDescription(event.target.value)} /></label>
              <button className="primary" disabled={!ticketSubject.trim() || !ticketDescription.trim()} onClick={() => void submitTicket()}>Reportar</button>
            </div>
            <div className="ds-map-list">
              <header>
                <h2>Tickets del proyecto</h2>
                <select value={ticketStatusFilter} onChange={(event) => setTicketStatusFilter(event.target.value)}>
                  <option value="">Todos los estados</option>
                  <option value="open">Abierto</option>
                  <option value="auto_resolved">Auto-resuelto</option>
                  <option value="resolved">Resuelto</option>
                </select>
              </header>
              {!tickets.length ? <p>Sin tickets registrados.</p> : null}
              {tickets.map((ticket) => (
                <article key={ticket.id} className="ds-map-card">
                  <strong>{ticket.subject}</strong>
                  <span className={`wa-status ${ticketStatusClass(ticket.status)}`}>{ticketStatusLabel(ticket.status)}</span>
                  <p>{ticket.description}</p>
                  {ticket.auto_response_text ? <small>Respuesta automática: {ticket.auto_response_text}</small> : null}
                  <small>{new Date(ticket.created_at).toLocaleString()}</small>
                  {ticket.status === 'open' ? <button onClick={() => void submitResolveTicket(ticket.id)}>Marcar resuelto</button> : null}
                </article>
              ))}
            </div>
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
