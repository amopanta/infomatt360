import { useEffect, useState } from 'react';

import { BrandLogo } from '../../components/BrandLogo';
import { useI18n } from '../../i18n';
import { bootstrapInstallation, fetchInstallRequirements, fetchInstallStatus } from './api';
import type { BootstrapPayload, BootstrapResult, InstallRequirements } from './api';

type Step = 0 | 1 | 2 | 3 | 4 | 5 | 6;

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

function slugify(value: string): string {
  return value
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '');
}

export function InstallWizardApp() {
  const { t } = useI18n();
  const [checking, setChecking] = useState(true);
  const [installed, setInstalled] = useState(true);
  const [step, setStep] = useState<Step>(0);
  const [form, setForm] = useState<BootstrapPayload>(EMPTY_FORM);
  const [slugTouched, setSlugTouched] = useState(false);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<BootstrapResult | null>(null);

  const [requirements, setRequirements] = useState<InstallRequirements | null>(null);
  const [requirementsError, setRequirementsError] = useState('');

  const [mailEnabled, setMailEnabled] = useState(false);
  const [mailSenderEmail, setMailSenderEmail] = useState('');
  const [mailHost, setMailHost] = useState('');
  const [mailPort, setMailPort] = useState('');

  const [storageEnabled, setStorageEnabled] = useState(true);
  const [storageMaxFileSizeMb, setStorageMaxFileSizeMb] = useState(25);

  const [backupEnabled, setBackupEnabled] = useState(false);
  const [backupFrequency, setBackupFrequency] = useState<'hourly' | 'daily' | 'weekly'>('daily');

  const STEP_LABELS = [
    t('install.stepRequirements'), t('install.stepOrganization'), t('install.stepAdmin'),
    t('install.stepMail'), t('install.stepStorage'), t('install.stepBackups'), t('install.stepConfirm'),
  ] as const;

  useEffect(() => {
    fetchInstallStatus()
      .then((status) => setInstalled(status.installed))
      .catch(() => setInstalled(true))
      .finally(() => setChecking(false));
  }, []);

  useEffect(() => {
    if (checking || installed) return;
    fetchInstallRequirements()
      .then(setRequirements)
      .catch(() => setRequirementsError(t('install.requirementsError')));
  }, [checking, installed]);

  function updateField(field: keyof BootstrapPayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function updateOrganizationName(value: string) {
    setForm((current) => ({
      ...current,
      organization_name: value,
      organization_slug: slugTouched ? current.organization_slug : slugify(value),
    }));
  }

  function goNext() {
    setError('');
    setStep((current) => (current < 6 ? ((current + 1) as Step) : current));
  }

  function goBack() {
    setError('');
    setStep((current) => (current > 0 ? ((current - 1) as Step) : current));
  }

  async function submit() {
    setError('');
    setSubmitting(true);
    try {
      const payload: BootstrapPayload = {
        ...form,
        organization_public_url: form.organization_public_url || undefined,
        mail: mailEnabled ? { sender_email: mailSenderEmail, server_host: mailHost || undefined, server_port: mailPort || undefined } : undefined,
        storage: storageEnabled ? { max_file_size_mb: storageMaxFileSizeMb } : undefined,
        backup: backupEnabled ? { frequency: backupFrequency } : undefined,
      };
      const created = await bootstrapInstallation(payload);
      setResult(created);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : t('install.installError'));
    } finally {
      setSubmitting(false);
    }
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

  if (installed) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <BrandLogo />
          <h1>{t('install.alreadyInstalledTitle')}</h1>
          <p>{t('install.alreadyInstalledDescription')}</p>
          <a href="/">{t('install.goToLogin')}</a>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card wizard-card">
        <BrandLogo />
        <h1>{t('install.title')}</h1>
        <ul className="wizard-steps">
          {STEP_LABELS.map((label, index) => (
            <li key={label} className={index === step ? 'active' : index < step ? 'done' : undefined}>{index + 1}. {label}</li>
          ))}
        </ul>

        {step === 0 ? (
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
            <p><small>{t('install.databaseNote')}</small></p>
          </fieldset>
        ) : null}

        {step === 1 ? (
          <fieldset className="wizard-fieldset">
            <label>{t('install.orgName')}<input required value={form.organization_name} onChange={(event) => updateOrganizationName(event.target.value)} /></label>
            <label>{t('install.orgSlug')}<input required pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" value={form.organization_slug} onChange={(event) => { setSlugTouched(true); updateField('organization_slug', event.target.value); }} /></label>
            <label>{t('install.orgUrl')}<input type="url" placeholder={t('install.orgUrlPlaceholder')} value={form.organization_public_url ?? ''} onChange={(event) => updateField('organization_public_url', event.target.value)} /></label>
          </fieldset>
        ) : null}

        {step === 2 ? (
          <fieldset className="wizard-fieldset">
            <label>{t('install.projectName')}<input required value={form.project_name} onChange={(event) => updateField('project_name', event.target.value)} /></label>
            <label>{t('install.adminFullName')}<input required value={form.admin_full_name} onChange={(event) => updateField('admin_full_name', event.target.value)} /></label>
            <label>{t('install.adminDocumentId')}<input required value={form.admin_document_id} onChange={(event) => updateField('admin_document_id', event.target.value)} /></label>
            <label>{t('install.adminEmail')}<input type="email" required value={form.admin_email} onChange={(event) => updateField('admin_email', event.target.value)} /></label>
            <label>{t('install.adminPassword')}<input type="password" required minLength={10} value={form.admin_password} onChange={(event) => updateField('admin_password', event.target.value)} /></label>
          </fieldset>
        ) : null}

        {step === 3 ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={mailEnabled} onChange={(event) => setMailEnabled(event.target.checked)} /> {t('install.configureMailNow')}</label>
            {mailEnabled ? (
              <>
                <label>{t('install.senderEmail')}<input type="email" required={mailEnabled} value={mailSenderEmail} onChange={(event) => setMailSenderEmail(event.target.value)} /></label>
                <label>{t('install.smtpServer')}<input value={mailHost} onChange={(event) => setMailHost(event.target.value)} /></label>
                <label>{t('install.smtpPort')}<input value={mailPort} onChange={(event) => setMailPort(event.target.value)} /></label>
              </>
            ) : <p><small>{t('install.mailLater')}</small></p>}
          </fieldset>
        ) : null}

        {step === 4 ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={storageEnabled} onChange={(event) => setStorageEnabled(event.target.checked)} /> {t('install.createLocalStorage')}</label>
            {storageEnabled ? (
              <label>{t('install.maxFileSize')}<input type="number" min={1} max={1000} value={storageMaxFileSizeMb} onChange={(event) => setStorageMaxFileSizeMb(Number(event.target.value) || 25)} /></label>
            ) : null}
            <p><small>{t('install.storageLater')}</small></p>
          </fieldset>
        ) : null}

        {step === 5 ? (
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

        {step === 6 ? (
          <fieldset className="wizard-fieldset">
            <p>{t('install.reviewBeforeInstall')}</p>
            <ul className="wizard-summary">
              <li><strong>{t('install.summaryOrg')}</strong> {form.organization_name} ({form.organization_slug})</li>
              <li><strong>{t('install.summaryProject')}</strong> {form.project_name}</li>
              <li><strong>{t('install.summaryAdmin')}</strong> {form.admin_full_name} ({form.admin_email})</li>
              <li><strong>{t('install.summaryMail')}</strong> {mailEnabled ? mailSenderEmail : t('install.notConfiguredYet')}</li>
              <li><strong>{t('install.summaryStorage')}</strong> {storageEnabled ? t('install.localStorageSummary', { size: storageMaxFileSizeMb }) : t('install.notConfiguredYet')}</li>
              <li><strong>{t('install.summaryBackups')}</strong> {backupEnabled ? t('install.autoBackupSummary', { frequency: backupFrequency }) : t('install.notConfiguredYet')}</li>
            </ul>
          </fieldset>
        ) : null}

        {error ? <p role="alert">{error}</p> : null}

        <div className="wizard-actions">
          <button type="button" className="secondary" disabled={step === 0} onClick={goBack}>{t('install.back')}</button>
          {step < 6 ? (
            <button type="button" onClick={goNext}>{t('install.next')}</button>
          ) : (
            <button type="button" disabled={submitting} onClick={() => void submit()}>{submitting ? t('install.installing') : t('install.completeInstall')}</button>
          )}
        </div>
      </div>
    </div>
  );
}
