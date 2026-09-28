import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { createMailProfile, fetchMailProfiles, suggestMailAutoconfig, testSendMailProfile } from './mailApi';
import type { MailProfile } from './mailApi';
import { createScheduledMailPollTask, fetchScheduledTasks } from './schedulerApi';
import type { ScheduledTask } from './schedulerApi';

const SMTP_PRESETS = {
  gmail: { label: 'Gmail / Google Workspace', host: 'smtp.gmail.com', port: '587', security: 'starttls', help: 'Google puede pedir una contraseña de aplicación con verificación en dos pasos.' },
  outlook: { label: 'Outlook.com / Hotmail / Live', host: 'smtp-mail.outlook.com', port: '587', security: 'starttls', help: 'Microsoft exige OAuth2 para Outlook.com. Infomatt360 aún no ofrece esa vinculación; completar los datos no garantiza el envío.' },
  microsoft365: { label: 'Microsoft 365 empresarial', host: 'smtp.office365.com', port: '587', security: 'starttls', help: 'El administrador debe habilitar SMTP AUTH para el buzón. Algunas organizaciones exigen OAuth2, aún no disponible aquí.' },
  yahoo: { label: 'Yahoo Mail', host: 'smtp.mail.yahoo.com', port: '587', security: 'starttls', help: 'Yahoo puede pedir una contraseña de aplicación para conectar servicios externos.' },
  zoho: { label: 'Zoho Mail personal', host: 'smtp.zoho.com', port: '587', security: 'starttls', help: 'Si tu cuenta Zoho usa un dominio empresarial, el servidor suele ser smtppro.zoho.com: confírmalo en Zoho.' },
} as const;
type SmtpPreset = keyof typeof SMTP_PRESETS | 'custom';

export function MailProfilesApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [profiles, setProfiles] = useState<MailProfile[]>([]);
  const [mailPollTasks, setMailPollTasks] = useState<ScheduledTask[]>([]);
  const [message, setMessage] = useState('');
  const [testMessages, setTestMessages] = useState<Record<string, string>>({});
  const [activatingId, setActivatingId] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [provider, setProvider] = useState<'smtp' | 'imap'>('smtp');
  const [smtpPreset, setSmtpPreset] = useState<SmtpPreset>('custom');
  const [senderEmail, setSenderEmail] = useState('');
  const [serverHost, setServerHost] = useState('');
  const [serverPort, setServerPort] = useState('');
  const [security, setSecurity] = useState<'starttls' | 'ssl' | 'none'>('starttls');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [autoconfigNote, setAutoconfigNote] = useState('');
  const [creating, setCreating] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  async function loadProfiles() {
    if (!projectId) return;
    try {
      setProfiles(await fetchMailProfiles(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar los perfiles de correo.');
    }
  }

  async function loadMailPollTasks() {
    if (!projectId) return;
    try {
      const tasks = await fetchScheduledTasks(projectId);
      setMailPollTasks(tasks.filter((task) => task.task_type === 'mail_poll'));
    } catch {
      setMailPollTasks([]);
    }
  }

  useEffect(() => { void loadProfiles(); void loadMailPollTasks(); }, [projectId]);

  async function submitActivatePolling(profile: MailProfile) {
    setActivatingId(profile.id);
    try {
      await createScheduledMailPollTask(projectId, profile.id, profile.name);
      setMessage('Sondeo IMAP activado: se ejecuta cada hora desde el worker de tareas programadas.');
      await loadMailPollTasks();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible activar el sondeo IMAP.');
    } finally {
      setActivatingId(null);
    }
  }

  async function handleEmailBlur() {
    const email = senderEmail.trim();
    if (provider !== 'smtp' || smtpPreset !== 'custom' || !email.includes('@')) return;
    try {
      const suggestion = await suggestMailAutoconfig(email);
      if (suggestion.found) {
        setServerHost(suggestion.server_host ?? '');
        setServerPort(suggestion.server_port ?? '');
        setSecurity(suggestion.use_tls === false ? 'none' : 'starttls');
        setAutoconfigNote(`Servidor sugerido automaticamente para ${email.split('@')[1]}.`);
      } else {
        setAutoconfigNote('Usa los datos SMTP de tu proveedor o de tu hosting: servidor, puerto, seguridad y credenciales.');
      }
    } catch {
      setAutoconfigNote('');
    }
  }

  function chooseSmtpPreset(next: SmtpPreset) {
    setSmtpPreset(next);
    if (next === 'custom') {
      setServerHost('');
      setServerPort('');
      setAutoconfigNote('Para correo del hosting, consulta servidor SMTP, puerto y seguridad en el panel de tu proveedor.');
      return;
    }
    const preset = SMTP_PRESETS[next];
    setServerHost(preset.host);
    setServerPort(preset.port);
    setSecurity(preset.security);
    if (senderEmail.trim() && !username.trim()) setUsername(senderEmail.trim());
    setAutoconfigNote(preset.help);
  }

  async function submitCreate() {
    setCreating(true);
    try {
      await createMailProfile({
        projectId,
        name: name.trim() || senderEmail.trim(),
        provider,
        senderEmail: senderEmail.trim(),
        serverHost: serverHost.trim(),
        serverPort: serverPort.trim(),
        security,
        username: username.trim(),
        password,
        isDefault,
      });
      setMessage(
        provider === 'imap'
          ? 'Perfil IMAP creado. Actívalo en la tabla de abajo para empezar a sondear la bandeja externa.'
          : 'Perfil de correo creado. Usa "Enviar prueba" para validar el envio real.',
      );
      setName('');
      setSenderEmail('');
      setServerHost('');
      setServerPort('');
      setUsername('');
      setPassword('');
      setIsDefault(false);
      setSecurity('starttls');
      setSmtpPreset('custom');
      setAutoconfigNote('');
      await loadProfiles();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear el perfil de correo.');
    } finally {
      setCreating(false);
    }
  }

  async function submitTestSend(profileId: string) {
    setTestingId(profileId);
    try {
      const result = await testSendMailProfile(profileId);
      setTestMessages((current) => ({ ...current, [profileId]: result.detail }));
    } catch (error) {
      setTestMessages((current) => ({ ...current, [profileId]: error instanceof Error ? error.message : 'No fue posible enviar el correo de prueba.' }));
    } finally {
      setTestingId(null);
    }
  }

  return (
    <AppShell title="Cuentas de correo">
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>Nuevo perfil de correo</h2>
              <p>Selecciona tu servicio para completar automáticamente el servidor y la seguridad, o usa los datos de tu hosting.</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>Tipo
              <select value={provider} onChange={(event) => { setProvider(event.target.value as 'smtp' | 'imap'); setSmtpPreset('custom'); setServerHost(''); setServerPort(''); setAutoconfigNote(''); }}>
                <option value="smtp">Envío (SMTP)</option>
                <option value="imap">Bandeja externa de solo lectura (IMAP)</option>
              </select>
            </label>
            {provider === 'smtp' ? <label>Servicio de correo
              <select value={smtpPreset} onChange={(event) => chooseSmtpPreset(event.target.value as SmtpPreset)}>
                <option value="custom">Otro proveedor o correo del hosting</option>
                {Object.entries(SMTP_PRESETS).map(([key, preset]) => <option key={key} value={key}>{preset.label}</option>)}
              </select>
            </label> : null}
            <label>Nombre<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Correo institucional" /></label>
            <label>{provider === 'imap' ? 'Casilla a leer' : 'Correo remitente'}<input type="email" value={senderEmail} onChange={(event) => { const previous = senderEmail.trim(); const next = event.target.value; setSenderEmail(next); if (!username.trim() || username.trim() === previous) setUsername(next); }} onBlur={() => void handleEmailBlur()} placeholder="notificaciones@midominio.com" /></label>
            <label>Servidor {provider === 'imap' ? 'IMAP' : 'SMTP'}<input value={serverHost} onChange={(event) => setServerHost(event.target.value)} placeholder={provider === 'imap' ? 'imap.midominio.com' : 'smtp.midominio.com'} /></label>
            <label>Puerto<input value={serverPort} onChange={(event) => setServerPort(event.target.value)} placeholder={provider === 'imap' ? '993' : security === 'ssl' ? '465' : '587'} /></label>
            <label>Usuario<input value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Normalmente, el correo completo" /></label>
            <label>Contraseña<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            {provider === 'smtp' ? <label>Seguridad SMTP<select value={security} onChange={(event) => { const next = event.target.value as 'starttls' | 'ssl' | 'none'; setSecurity(next); if (!serverPort || serverPort === '465' || serverPort === '587') setServerPort(next === 'ssl' ? '465' : '587'); }}><option value="starttls">STARTTLS (puerto 587)</option><option value="ssl">SSL/TLS (puerto 465)</option><option value="none">Sin cifrado (solo redes confiables)</option></select></label> : null}
            <label><input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} /> Predeterminado</label>
            <button className="primary" disabled={creating || !senderEmail.trim() || !serverHost.trim() || !serverPort.trim()} onClick={() => void submitCreate()}>
              {creating ? 'Creando…' : 'Crear perfil'}
            </button>
          </div>
          {provider === 'imap' ? <p>Bandeja de solo lectura: se sondea INBOX cada hora, sin adjuntos ni respuesta desde la app (ver docs/116).</p> : null}
          {provider === 'smtp' ? <p>Para usar esta cuenta en recuperación de contraseña, márcala como predeterminada y confirma el envío con “Enviar prueba”. Algunos proveedores requieren una contraseña de aplicación.</p> : null}
          {autoconfigNote ? <p>{autoconfigNote}</p> : null}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>Perfiles del proyecto</h2>
              <p>Envia un correo de prueba real antes de dar por buena la configuracion.</p>
            </div>
          </header>
          {!profiles.length ? <p>Aun no hay perfiles de correo para este proyecto.</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Tipo</th>
                  <th>Remitente</th>
                  <th>Servidor</th>
                  <th>Predeterminado</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => {
                  const mailPollTask = mailPollTasks.find((task) => task.target_id === profile.id);
                  return (
                    <tr key={profile.id}>
                      <td>{profile.name}</td>
                      <td>{profile.provider === 'imap' ? 'IMAP (lectura)' : 'SMTP'}</td>
                      <td>{profile.sender_email}</td>
                      <td>{profile.server_host ? `${profile.server_host}:${profile.server_port ?? ''}` : '—'}</td>
                      <td>{profile.is_default ? 'Si' : 'No'}</td>
                      <td>
                        {profile.provider === 'imap'
                          ? mailPollTask
                            ? `Sondeo activo (cada hora) — ${mailPollTask.last_result ?? 'aún sin ejecutar'}`
                            : 'Sondeo inactivo'
                          : testMessages[profile.id] ?? '—'}
                      </td>
                      <td>
                        {profile.provider === 'imap' ? (
                          mailPollTask ? null : (
                            <button disabled={activatingId === profile.id} onClick={() => void submitActivatePolling(profile)}>
                              {activatingId === profile.id ? 'Activando…' : 'Activar sondeo IMAP'}
                            </button>
                          )
                        ) : (
                          <button disabled={testingId === profile.id} onClick={() => void submitTestSend(profile.id)}>
                            {testingId === profile.id ? 'Enviando…' : 'Enviar prueba'}
                          </button>
                        )}
                      </td>
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
