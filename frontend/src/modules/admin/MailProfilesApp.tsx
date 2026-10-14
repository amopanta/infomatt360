import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
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
  zohoBusiness: { label: 'Zoho Mail empresarial', host: 'smtppro.zoho.com', port: '587', security: 'starttls', help: 'Usa el correo completo y la contraseña de aplicación si tienes autenticación de dos factores.' },
  icloud: { label: 'Apple iCloud Mail', host: 'smtp.mail.me.com', port: '587', security: 'starttls', help: 'Usa tu dirección completa de iCloud y una contraseña específica de aplicación de Apple.' },
  fastmail: { label: 'Fastmail', host: 'smtp.fastmail.com', port: '465', security: 'ssl', help: 'Fastmail requiere una contraseña de aplicación. Comprueba que tu plan permita acceso SMTP.' },
  gmx: { label: 'GMX', host: 'mail.gmx.com', port: '587', security: 'starttls', help: 'Activa el acceso de aplicaciones externas en GMX si tu cuenta lo requiere.' },
  protonBusiness: { label: 'Proton Mail (dominio propio y plan compatible)', host: 'smtp.protonmail.ch', port: '587', security: 'starttls', help: 'Solo para cuentas con SMTP submission habilitado y dominio propio. Usa el token SMTP generado en Proton como contraseña; la contraseña habitual no funciona.' },
} as const;
type SmtpPreset = keyof typeof SMTP_PRESETS | 'custom';

export function MailProfilesApp() {
  const { t } = useI18n();
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
      setMessage(error instanceof Error ? error.message : t('admin.mail.errorLoadProfiles'));
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
      setMessage(t('admin.mail.imapPollingActivated'));
      await loadMailPollTasks();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.mail.errorActivatePolling'));
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
        setAutoconfigNote(t('admin.mail.autoconfigSuggested', { domain: email.split('@')[1] }));
      } else {
        setAutoconfigNote(t('admin.mail.autoconfigManual'));
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
      setAutoconfigNote(t('admin.mail.autoconfigCustom'));
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
          ? t('admin.mail.imapProfileCreated')
          : t('admin.mail.smtpProfileCreated'),
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
      setMessage(error instanceof Error ? error.message : t('admin.mail.errorCreateProfile'));
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
      setTestMessages((current) => ({ ...current, [profileId]: error instanceof Error ? error.message : t('admin.mail.errorSendTest') }));
    } finally {
      setTestingId(null);
    }
  }

  return (
    <AppShell title={t('admin.mail.title')}>
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.mail.newProfileTitle')}</h2>
              <p>{t('admin.mail.newProfileDescription')}</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>{t('admin.mail.typeLabel')}
              <select value={provider} onChange={(event) => { setProvider(event.target.value as 'smtp' | 'imap'); setSmtpPreset('custom'); setServerHost(''); setServerPort(''); setAutoconfigNote(''); }}>
                <option value="smtp">{t('admin.mail.typeSMTP')}</option>
                <option value="imap">{t('admin.mail.typeIMAP')}</option>
              </select>
            </label>
            {provider === 'smtp' ? <label>{t('admin.mail.emailServiceLabel')}
              <select value={smtpPreset} onChange={(event) => chooseSmtpPreset(event.target.value as SmtpPreset)}>
                <option value="custom">{t('admin.mail.customProvider')}</option>
                {Object.entries(SMTP_PRESETS).map(([key, preset]) => <option key={key} value={key}>{preset.label}</option>)}
              </select>
            </label> : null}
            <label>{t('admin.mail.nameLabel')}<input value={name} onChange={(event) => setName(event.target.value)} placeholder={t('admin.mail.namePlaceholder')} /></label>
            <label>{provider === 'imap' ? t('admin.mail.imapMailboxLabel') : t('admin.mail.senderEmailLabel')}<input type="email" value={senderEmail} onChange={(event) => { const previous = senderEmail.trim(); const next = event.target.value; setSenderEmail(next); if (!username.trim() || username.trim() === previous) setUsername(next); }} onBlur={() => void handleEmailBlur()} placeholder={t('admin.mail.emailPlaceholder')} /></label>
            <label>{provider === 'imap' ? t('admin.mail.imapServerLabel') : t('admin.mail.smtpServerLabel')}<input value={serverHost} onChange={(event) => setServerHost(event.target.value)} placeholder={provider === 'imap' ? t('admin.mail.imapServerPlaceholder') : t('admin.mail.smtpServerPlaceholder')} /></label>
            <label>{t('admin.mail.portLabel')}<input value={serverPort} onChange={(event) => setServerPort(event.target.value)} placeholder={provider === 'imap' ? '993' : security === 'ssl' ? '465' : '587'} /></label>
            <label>{t('admin.mail.usernameLabel')}<input value={username} onChange={(event) => setUsername(event.target.value)} placeholder={t('admin.mail.usernamePlaceholder')} /></label>
            <label>{t('admin.mail.passwordLabel')}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            {provider === 'smtp' ? <label>{t('admin.mail.smtpSecurityLabel')}<select value={security} onChange={(event) => { const next = event.target.value as 'starttls' | 'ssl' | 'none'; setSecurity(next); if (!serverPort || serverPort === '465' || serverPort === '587') setServerPort(next === 'ssl' ? '465' : '587'); }}><option value="starttls">{t('admin.mail.securityStartTLS')}</option><option value="ssl">{t('admin.mail.securitySSL')}</option><option value="none">{t('admin.mail.securityNone')}</option></select></label> : null}
            <label><input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} /> {t('admin.mail.defaultCheckbox')}</label>
            <button className="primary" disabled={creating || !senderEmail.trim() || !serverHost.trim() || !serverPort.trim()} onClick={() => void submitCreate()}>
              {creating ? t('admin.mail.creating') : t('admin.mail.createProfile')}
            </button>
          </div>
          {provider === 'imap' ? <p>{t('admin.mail.imapNote')}</p> : null}
          {provider === 'smtp' ? <p>{t('admin.mail.smtpNote')}</p> : null}
          {autoconfigNote ? <p>{autoconfigNote}</p> : null}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.mail.profilesTitle')}</h2>
              <p>{t('admin.mail.profilesDescription')}</p>
            </div>
          </header>
          {!profiles.length ? <p>{t('admin.mail.noProfilesYet')}</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('admin.mail.colName')}</th>
                  <th>{t('admin.mail.colType')}</th>
                  <th>{t('admin.mail.colSender')}</th>
                  <th>{t('admin.mail.colServer')}</th>
                  <th>{t('admin.mail.colDefault')}</th>
                  <th>{t('admin.mail.colStatus')}</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => {
                  const mailPollTask = mailPollTasks.find((task) => task.target_id === profile.id);
                  return (
                    <tr key={profile.id}>
                      <td>{profile.name}</td>
                      <td>{profile.provider === 'imap' ? t('admin.mail.typeImapRead') : t('admin.mail.typeSMTPShort')}</td>
                      <td>{profile.sender_email}</td>
                      <td>{profile.server_host ? `${profile.server_host}:${profile.server_port ?? ''}` : '—'}</td>
                      <td>{profile.is_default ? t('admin.mail.defaultYes') : t('admin.mail.defaultNo')}</td>
                      <td>
                        {profile.provider === 'imap'
                          ? mailPollTask
                            ? t('admin.mail.pollingActive', { result: mailPollTask.last_result ?? t('admin.mail.pollingNotRun') })
                            : t('admin.mail.pollingInactive')
                          : testMessages[profile.id] ?? '—'}
                      </td>
                      <td>
                        {profile.provider === 'imap' ? (
                          mailPollTask ? null : (
                            <button disabled={activatingId === profile.id} onClick={() => void submitActivatePolling(profile)}>
                              {activatingId === profile.id ? t('admin.mail.activatingPolling') : t('admin.mail.activatePolling')}
                            </button>
                          )
                        ) : (
                          <button disabled={testingId === profile.id} onClick={() => void submitTestSend(profile.id)}>
                            {testingId === profile.id ? t('admin.mail.sending') : t('admin.mail.sendTest')}
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
