import { useEffect, useState } from 'react';

import { BrandLogo } from '../../components/BrandLogo';
import { useI18n } from '../../i18n';
import {
  applyDatabase, bootstrapInstallation, fetchInstallRequirements, fetchInstallStatus, recoverAdmin, storeInstallCode,
  storedInstallCode, testDatabase, testMail, verifyInstallCode, waitForServer,
} from './api';
import type { BootstrapPayload, BootstrapResult, DatabaseCheck, DatabaseSetup, InstallRequirements, MailServer } from './api';

// Pasos del asistente (docs/151). El código va primero: sin él no se puede
// cambiar nada. La base de datos va antes de crear la organización porque
// todo lo demás se guarda en ella.
type Step = 'code' | 'requirements' | 'database' | 'organization' | 'admin' | 'mail' | 'storage' | 'backups' | 'confirm';
const STEPS: Step[] = ['code', 'requirements', 'database', 'organization', 'admin', 'mail', 'storage', 'backups', 'confirm'];
const STEP_KEY = 'infomatt360_install_step';

const EMPTY_FORM: BootstrapPayload = {
  organization_name: '',
  organization_slug: '',
  organization_public_url: '',
  project_name: '',
  admin_full_name: '',
  admin_document_id: '',
  admin_email: '',
  admin_password: '',
};

const EMPTY_DATABASE: DatabaseSetup = { mode: 'bundled', host: '', port: 5432, name: 'infomatt360', username: '', password: '', sslmode: null };
const EMPTY_MAIL: MailServer = { host: '', port: 587, username: '', password: '', use_tls: true, sender_email: '', test_recipient: '' };

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

function passwordProblem(t: (key: string) => string, password: string, confirm: string): string {
  if (password.length < 10) return t('install.passwordTooShort');
  if (!/[a-zA-Z]/.test(password) || !/\d/.test(password)) return t('install.passwordNeedsMix');
  if (password !== confirm) return t('install.passwordMismatch');
  return '';
}

export function InstallWizardApp() {
  const { t } = useI18n();
  const [checking, setChecking] = useState(true);
  const [installed, setInstalled] = useState(true);
  const [enforced, setEnforced] = useState(false);
  // Tras recargar la página se conservan el código y el paso, pero no lo
  // escrito (y nunca las contraseñas): desde la organización se vuelve a pedir.
  const [step, setStep] = useState<Step>(() => {
    try {
      const saved = sessionStorage.getItem(STEP_KEY) as Step | null;
      if (!saved || !STEPS.includes(saved) || !storedInstallCode()) return 'code';
      return STEPS.indexOf(saved) > STEPS.indexOf('organization') ? 'organization' : saved;
    } catch { return 'code'; }
  });
  const [form, setForm] = useState<BootstrapPayload>(EMPTY_FORM);
  const [confirmPassword, setConfirmPassword] = useState('');
  const [slugTouched, setSlugTouched] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<BootstrapResult | null>(null);

  const [code, setCode] = useState(storedInstallCode());
  const [requirements, setRequirements] = useState<InstallRequirements | null>(null);
  const [requirementsError, setRequirementsError] = useState('');

  const [database, setDatabase] = useState<DatabaseSetup>(EMPTY_DATABASE);
  const [databaseCheck, setDatabaseCheck] = useState<DatabaseCheck | null>(null);

  const [mailEnabled, setMailEnabled] = useState(false);
  const [mail, setMail] = useState<MailServer>(EMPTY_MAIL);
  const [mailTested, setMailTested] = useState(false);

  const [storageEnabled, setStorageEnabled] = useState(true);
  const [storageMaxFileSizeMb, setStorageMaxFileSizeMb] = useState(25);

  const [backupEnabled, setBackupEnabled] = useState(false);
  const [backupFrequency, setBackupFrequency] = useState<'hourly' | 'daily' | 'weekly'>('daily');

  const STEP_LABELS: Record<Step, string> = {
    code: t('install.stepCode'), requirements: t('install.stepRequirements'), database: t('install.stepDatabase'),
    organization: t('install.stepOrganization'), admin: t('install.stepAdmin'), mail: t('install.stepMail'),
    storage: t('install.stepStorage'), backups: t('install.stepBackups'), confirm: t('install.stepConfirm'),
  };
  const index = STEPS.indexOf(step);

  useEffect(() => {
    fetchInstallStatus()
      .then((status) => { setInstalled(status.installed); setEnforced(status.installer_enforced); })
      .catch(() => setInstalled(true))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => { try { sessionStorage.setItem(STEP_KEY, step); } catch { /* opcional */ } }, [step]);

  useEffect(() => {
    if (checking || installed || step !== 'requirements') return;
    fetchInstallRequirements()
      .then(setRequirements)
      .catch(() => setRequirementsError(t('install.requirementsError')));
  }, [checking, installed, step]);

  function updateField(field: keyof BootstrapPayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateOrganizationName(value: string) {
    setForm((current) => ({ ...current, organization_name: value, organization_slug: slugTouched ? current.organization_slug : slugify(value) }));
  }

  function go(next: Step) { setError(''); setNotice(''); setStep(next); }

  async function run(action: () => Promise<void>) {
    setError(''); setNotice(''); setBusy(true);
    try { await action(); } catch (reason) { setError(reason instanceof Error ? reason.message : t('install.installError')); } finally { setBusy(false); }
  }

  /** Primer paso con datos incompletos, para revisar todo antes de instalar. */
  function incompleteStep(): { step: Step; message: string } | null {
    if (form.organization_name.trim().length < 2 || form.organization_slug.length < 2 || form.project_name.trim().length < 3) return { step: 'organization', message: t('install.completeOrganization') };
    if (form.admin_full_name.trim().length < 3 || form.admin_document_id.trim().length < 5 || !form.admin_email.includes('@')) return { step: 'admin', message: t('install.completeAdmin') };
    const problem = passwordProblem(t, form.admin_password, confirmPassword);
    if (problem) return { step: 'admin', message: problem };
    if (mailEnabled && (!mail.host || !mail.sender_email)) return { step: 'mail', message: t('install.completeMail') };
    return null;
  }

  /** Valida lo del paso actual antes de avanzar. */
  async function next() {
    if (step === 'code') {
      await run(async () => { storeInstallCode(code.trim()); await verifyInstallCode(code.trim()); go('requirements'); });
      return;
    }
    if (step === 'requirements' && requirements && !requirements.ready) { setError(t('install.fixRequirements')); return; }
    if (step === 'database') {
      if (database.mode === 'bundled') { go('organization'); return; }
      await run(async () => {
        const applied = await applyDatabase(database);
        setDatabaseCheck(applied);
        if (applied.restarting) {
          setNotice(t('install.databaseRestarting'));
          if (!(await waitForServer())) throw new Error(t('install.databaseRestartTimeout'));
        }
        go('organization');
      });
      return;
    }
    if (step === 'organization' && (form.organization_name.trim().length < 2 || form.organization_slug.length < 2 || form.project_name.trim().length < 3)) { setError(t('install.completeOrganization')); return; }
    if (step === 'admin') {
      if (form.admin_full_name.trim().length < 3 || form.admin_document_id.trim().length < 5 || !form.admin_email.includes('@')) { setError(t('install.completeAdmin')); return; }
      const problem = passwordProblem(t, form.admin_password, confirmPassword);
      if (problem) { setError(problem); return; }
    }
    if (step === 'mail' && mailEnabled && (!mail.host || !mail.sender_email)) { setError(t('install.completeMail')); return; }
    go(STEPS[index + 1]);
  }

  async function checkDatabase() {
    await run(async () => { const checked = await testDatabase(database); setDatabaseCheck(checked); setNotice(checked.usable ? t('install.databaseOk', { version: checked.server_version ?? '' }) : ''); if (!checked.usable) setError(t('install.databaseForeign', { tables: checked.foreign_tables.join(', ') })); });
  }

  async function sendTestMail() {
    await run(async () => { await testMail({ ...mail, test_recipient: mail.test_recipient || form.admin_email }); setMailTested(true); setNotice(t('install.mailTestSent', { email: mail.test_recipient || form.admin_email })); });
  }

  async function submit() {
    const missing = incompleteStep();
    if (missing) { setStep(missing.step); setError(missing.message); return; }
    await run(async () => {
      const payload: BootstrapPayload = {
        ...form,
        organization_public_url: form.organization_public_url || undefined,
        mail: mailEnabled ? { sender_email: mail.sender_email, server_host: mail.host || undefined, server_port: String(mail.port), username: mail.username, password: mail.password, use_tls: mail.use_tls } : undefined,
        storage: storageEnabled ? { max_file_size_mb: storageMaxFileSizeMb } : undefined,
        backup: backupEnabled ? { frequency: backupFrequency } : undefined,
      };
      setResult(await bootstrapInstallation(payload));
      storeInstallCode('');
      try { sessionStorage.removeItem(STEP_KEY); } catch { /* opcional */ }
    });
  }

  if (checking) return <div className="auth-page"><p>{t('install.checking')}</p></div>;

  if (result) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <BrandLogo />
          <h1>{t('install.completeTitle')}</h1>
          <p>{t('install.completeDescription')}</p>
          <ul className="wizard-summary">
            <li><strong>{t('install.summaryMail')}</strong> {result.mail_profile_id ? t('install.mailConfigured') : t('install.mailPending')}</li>
            <li><strong>{t('install.summaryStorage')}</strong> {result.storage_profile_id ? t('install.storageCreated') : t('install.storagePending')}</li>
            <li><strong>{t('install.summaryBackups')}</strong> {result.scheduled_task_id ? t('install.backupActivated') : t('install.backupPending')}</li>
          </ul>
          <a href="/">{t('install.goToLogin')}</a>
        </div>
      </div>
    );
  }

  if (installed) return <RecoverAdminPanel enforced={enforced} />;

  return (
    <div className="auth-page">
      <div className="auth-card wizard-card">
        <BrandLogo />
        <h1>{t('install.title')}</h1>
        <ol className="wizard-steps" aria-label={t('install.stepsAria')}>
          {STEPS.map((item, position) => (
            <li key={item} className={item === step ? 'active' : position < index ? 'done' : undefined} aria-current={item === step ? 'step' : undefined}>{position + 1}. {STEP_LABELS[item]}</li>
          ))}
        </ol>

        {step === 'code' ? (
          <fieldset className="wizard-fieldset">
            <p>{t('install.codeDescription')}</p>
            <pre className="wizard-command">docker compose -f docker-compose.production.example.yml --env-file .env.production exec backend-1 python -m app.cli.install_code</pre>
            <label>{t('install.codeLabel')}<input autoComplete="one-time-code" placeholder="XXXX-XXXX-XXXX" value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} /></label>
          </fieldset>
        ) : null}

        {step === 'requirements' ? (
          <fieldset className="wizard-fieldset">
            <p>{t('install.requirementsDescription')}</p>
            {requirementsError ? <p role="alert">{requirementsError}</p> : null}
            {requirements ? (
              <ul className="requirement-list">
                {requirements.checks.map((check) => (
                  <li key={check.key} className={`requirement-check status-${check.status}`}>
                    <span>{check.label}</span>
                    {check.detail ? <small>{check.detail}</small> : null}
                  </li>
                ))}
              </ul>
            ) : !requirementsError ? <p>{t('install.verifying')}</p> : null}
          </fieldset>
        ) : null}

        {step === 'database' ? (
          <fieldset className="wizard-fieldset">
            <p>{t('install.databaseDescription')}</p>
            <div className="wizard-choice" role="radiogroup" aria-label={t('install.stepDatabase')}>
              <label className={database.mode === 'bundled' ? 'selected' : undefined}><input type="radio" name="db-mode" checked={database.mode === 'bundled'} onChange={() => { setDatabase({ ...database, mode: 'bundled' }); setDatabaseCheck(null); }} /><span><strong>{t('install.databaseBundled')}</strong><small>{t('install.databaseBundledText')}</small></span></label>
              <label className={database.mode === 'external' ? 'selected' : undefined}><input type="radio" name="db-mode" checked={database.mode === 'external'} onChange={() => { setDatabase({ ...database, mode: 'external' }); setDatabaseCheck(null); }} /><span><strong>{t('install.databaseExternal')}</strong><small>{t('install.databaseExternalText')}</small></span></label>
            </div>
            {database.mode === 'external' ? (
              <div className="wizard-grid">
                <label className="wizard-wide">{t('install.dbHost')}<input value={database.host} placeholder="db.ejemplo.org" onChange={(event) => setDatabase({ ...database, host: event.target.value })} /></label>
                <label>{t('install.dbPort')}<input type="number" value={database.port} onChange={(event) => setDatabase({ ...database, port: Number(event.target.value) || 5432 })} /></label>
                <label>{t('install.dbName')}<input value={database.name} onChange={(event) => setDatabase({ ...database, name: event.target.value })} /></label>
                <label>{t('install.dbUser')}<input autoComplete="off" value={database.username} onChange={(event) => setDatabase({ ...database, username: event.target.value })} /></label>
                <label>{t('install.dbPassword')}<input type="password" autoComplete="new-password" value={database.password} onChange={(event) => setDatabase({ ...database, password: event.target.value })} /></label>
                <label className="wizard-wide">{t('install.dbSsl')}<select value={database.sslmode ?? ''} onChange={(event) => setDatabase({ ...database, sslmode: event.target.value || null })}>
                  <option value="">{t('install.dbSslDefault')}</option><option value="require">{t('install.dbSslRequire')}</option><option value="verify-full">{t('install.dbSslVerify')}</option><option value="disable">{t('install.dbSslDisable')}</option>
                </select></label>
                <div className="wizard-wide"><button type="button" className="secondary" disabled={busy || !database.host || !database.username} onClick={() => void checkDatabase()}>{t('install.dbTest')}</button></div>
                {databaseCheck?.usable ? <p className="wizard-wide wizard-ok">{databaseCheck.empty ? t('install.databaseEmpty') : t('install.databaseExisting', { revision: databaseCheck.current_revision ?? '' })}</p> : null}
              </div>
            ) : null}
          </fieldset>
        ) : null}

        {step === 'organization' ? (
          <fieldset className="wizard-fieldset">
            <label>{t('install.orgName')}<input required value={form.organization_name} onChange={(event) => updateOrganizationName(event.target.value)} /></label>
            <label>{t('install.orgSlug')}<input required pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" value={form.organization_slug} onChange={(event) => { setSlugTouched(true); updateField('organization_slug', event.target.value); }} /><small>{t('install.orgSlugHelp')}</small></label>
            <label>{t('install.orgUrl')}<input type="url" placeholder={t('install.orgUrlPlaceholder')} value={form.organization_public_url ?? ''} onChange={(event) => updateField('organization_public_url', event.target.value)} /></label>
            <label>{t('install.projectName')}<input required value={form.project_name} onChange={(event) => updateField('project_name', event.target.value)} /></label>
          </fieldset>
        ) : null}

        {step === 'admin' ? (
          <fieldset className="wizard-fieldset">
            <p>{t('install.adminDescription')}</p>
            <label>{t('install.adminFullName')}<input required value={form.admin_full_name} onChange={(event) => updateField('admin_full_name', event.target.value)} /></label>
            <label>{t('install.adminDocumentId')}<input required value={form.admin_document_id} onChange={(event) => updateField('admin_document_id', event.target.value)} /></label>
            <label>{t('install.adminEmail')}<input type="email" required autoComplete="username" value={form.admin_email} onChange={(event) => updateField('admin_email', event.target.value)} /></label>
            <label>{t('install.adminPassword')}<input type="password" required minLength={10} autoComplete="new-password" value={form.admin_password} onChange={(event) => updateField('admin_password', event.target.value)} /><small>{t('install.passwordHelp')}</small></label>
            <label>{t('install.adminPasswordConfirm')}<input type="password" required autoComplete="new-password" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} /></label>
          </fieldset>
        ) : null}

        {step === 'mail' ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={mailEnabled} onChange={(event) => setMailEnabled(event.target.checked)} /> {t('install.configureMailNow')}</label>
            {mailEnabled ? (
              <div className="wizard-grid">
                <label className="wizard-wide">{t('install.smtpServer')}<input value={mail.host} placeholder="smtp.gmail.com" onChange={(event) => { setMail({ ...mail, host: event.target.value }); setMailTested(false); }} /></label>
                <label>{t('install.smtpPort')}<input type="number" value={mail.port} onChange={(event) => { setMail({ ...mail, port: Number(event.target.value) || 587 }); setMailTested(false); }} /></label>
                <label className="wizard-toggle-row"><input type="checkbox" checked={mail.use_tls} onChange={(event) => setMail({ ...mail, use_tls: event.target.checked })} /> {t('install.smtpTls')}</label>
                <label>{t('install.smtpUser')}<input autoComplete="off" value={mail.username} onChange={(event) => { setMail({ ...mail, username: event.target.value }); setMailTested(false); }} /></label>
                <label>{t('install.smtpPassword')}<input type="password" autoComplete="new-password" value={mail.password} onChange={(event) => { setMail({ ...mail, password: event.target.value }); setMailTested(false); }} /><small>{t('install.smtpPasswordHelp')}</small></label>
                <label className="wizard-wide">{t('install.senderEmail')}<input type="email" value={mail.sender_email} onChange={(event) => setMail({ ...mail, sender_email: event.target.value })} /></label>
                <label className="wizard-wide">{t('install.mailTestTo')}<input type="email" placeholder={form.admin_email} value={mail.test_recipient} onChange={(event) => setMail({ ...mail, test_recipient: event.target.value })} /></label>
                <div className="wizard-wide"><button type="button" className="secondary" disabled={busy || !mail.host || !mail.sender_email} onClick={() => void sendTestMail()}>{t('install.mailSendTest')}</button>{mailTested ? <span className="wizard-ok"> {t('install.mailTestOk')}</span> : null}</div>
              </div>
            ) : <p><small>{t('install.mailLater')}</small></p>}
          </fieldset>
        ) : null}

        {step === 'storage' ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={storageEnabled} onChange={(event) => setStorageEnabled(event.target.checked)} /> {t('install.createLocalStorage')}</label>
            {storageEnabled ? (
              <label>{t('install.maxFileSize')}<input type="number" min={1} max={1000} value={storageMaxFileSizeMb} onChange={(event) => setStorageMaxFileSizeMb(Number(event.target.value) || 25)} /></label>
            ) : null}
            <p><small>{t('install.storageLater')}</small></p>
          </fieldset>
        ) : null}

        {step === 'backups' ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={backupEnabled} onChange={(event) => setBackupEnabled(event.target.checked)} /> {t('install.enableAutoBackup')}</label>
            {backupEnabled ? (
              <label>{t('install.frequencyLabel')}
                <select value={backupFrequency} onChange={(event) => setBackupFrequency(event.target.value as typeof backupFrequency)}>
                  <option value="hourly">{t('install.frequencyHourly')}</option>
                  <option value="daily">{t('install.frequencyDaily')}</option>
                  <option value="weekly">{t('install.frequencyWeekly')}</option>
                </select>
              </label>
            ) : <p><small>{t('install.backupLater')}</small></p>}
          </fieldset>
        ) : null}

        {step === 'confirm' ? (
          <fieldset className="wizard-fieldset">
            <p>{t('install.reviewBeforeInstall')}</p>
            <ul className="wizard-summary">
              <li><strong>{t('install.summaryDatabase')}</strong> {database.mode === 'bundled' ? t('install.databaseBundled') : `${database.host}:${database.port}/${database.name}`}</li>
              <li><strong>{t('install.summaryOrg')}</strong> {form.organization_name} ({form.organization_slug})</li>
              <li><strong>{t('install.summaryProject')}</strong> {form.project_name}</li>
              <li><strong>{t('install.summaryAdmin')}</strong> {form.admin_full_name} ({form.admin_email})</li>
              <li><strong>{t('install.summaryMail')}</strong> {mailEnabled ? `${mail.sender_email} · ${mail.host}${mailTested ? ` · ${t('install.mailTestOk')}` : ''}` : t('install.notConfiguredYet')}</li>
              <li><strong>{t('install.summaryStorage')}</strong> {storageEnabled ? t('install.localStorageSummary', { size: storageMaxFileSizeMb }) : t('install.notConfiguredYet')}</li>
              <li><strong>{t('install.summaryBackups')}</strong> {backupEnabled ? t('install.autoBackupSummary', { frequency: backupFrequency }) : t('install.notConfiguredYet')}</li>
            </ul>
          </fieldset>
        ) : null}

        {notice ? <p role="status" className="wizard-ok">{notice}</p> : null}
        {error ? <p role="alert">{error}</p> : null}

        <div className="wizard-actions">
          <button type="button" className="secondary" disabled={index === 0 || busy} onClick={() => go(STEPS[index - 1])}>{t('install.back')}</button>
          {step !== 'confirm' ? (
            <button type="button" disabled={busy || (step === 'code' && code.trim().length < 8)} onClick={() => void next()}>{busy ? t('install.working') : step === 'database' && database.mode === 'external' ? t('install.dbUse') : t('install.next')}</button>
          ) : (
            <button type="button" disabled={busy} onClick={() => void submit()}>{busy ? t('install.installing') : t('install.completeInstall')}</button>
          )}
        </div>
      </div>
    </div>
  );
}

/** Sistema ya instalado: entrar, o crear/recuperar un administrador con un
 * código de recuperación que se genera en el servidor (docs/151). */
function RecoverAdminPanel({ enforced }: { enforced: boolean }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState('');
  const [data, setData] = useState({ email: '', full_name: '', document_id: '', password: '' });
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState<{ created: boolean; email: string; projects: string[] } | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit() {
    setError('');
    const problem = passwordProblem(t, data.password, confirm);
    if (problem) { setError(problem); return; }
    setBusy(true);
    try {
      storeInstallCode(code.trim());
      setDone(await recoverAdmin(data));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('install.recoverError'));
    } finally {
      storeInstallCode('');
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="auth-card wizard-card">
        <BrandLogo />
        <h1>{t('install.alreadyInstalledTitle')}</h1>
        <p>{t('install.alreadyInstalledDescription')}</p>
        <a href="/">{t('install.goToLogin')}</a>
        {done ? (
          <p role="status" className="wizard-ok">{done.created ? t('install.recoverCreated', { email: done.email }) : t('install.recoverUpdated', { email: done.email })} {t('install.recoverProjects', { projects: done.projects.join(', ') })}</p>
        ) : !open ? (
          <button type="button" className="secondary" onClick={() => setOpen(true)}>{t('install.recoverOpen')}</button>
        ) : (
          <fieldset className="wizard-fieldset">
            <h2>{t('install.recoverTitle')}</h2>
            <p>{t('install.recoverDescription')}</p>
            <pre className="wizard-command">docker compose -f docker-compose.production.example.yml --env-file .env.production exec backend-1 python -m app.cli.install_code</pre>
            {!enforced ? <p><small>{t('install.recoverAlwaysCode')}</small></p> : null}
            <label>{t('install.recoverCode')}<input autoComplete="one-time-code" placeholder="XXXX-XXXX-XXXX" value={code} onChange={(event) => setCode(event.target.value.toUpperCase())} /></label>
            <label>{t('install.adminEmail')}<input type="email" autoComplete="username" value={data.email} onChange={(event) => setData({ ...data, email: event.target.value })} /></label>
            <label>{t('install.adminFullName')}<input value={data.full_name} onChange={(event) => setData({ ...data, full_name: event.target.value })} /><small>{t('install.recoverNewOnly')}</small></label>
            <label>{t('install.adminDocumentId')}<input value={data.document_id} onChange={(event) => setData({ ...data, document_id: event.target.value })} /><small>{t('install.recoverNewOnly')}</small></label>
            <label>{t('install.adminPassword')}<input type="password" autoComplete="new-password" value={data.password} onChange={(event) => setData({ ...data, password: event.target.value })} /><small>{t('install.passwordHelp')}</small></label>
            <label>{t('install.adminPasswordConfirm')}<input type="password" autoComplete="new-password" value={confirm} onChange={(event) => setConfirm(event.target.value)} /></label>
            {error ? <p role="alert">{error}</p> : null}
            <div className="wizard-actions">
              <button type="button" className="secondary" onClick={() => setOpen(false)}>{t('install.back')}</button>
              <button type="button" disabled={busy || code.trim().length < 8 || !data.email} onClick={() => void submit()}>{busy ? t('install.working') : t('install.recoverSubmit')}</button>
            </div>
          </fieldset>
        )}
      </div>
    </div>
  );
}
