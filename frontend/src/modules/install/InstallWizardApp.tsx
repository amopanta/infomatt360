import { useEffect, useState } from 'react';

import { BrandLogo } from '../../components/BrandLogo';
import { bootstrapInstallation, fetchInstallRequirements, fetchInstallStatus } from './api';
import type { BootstrapPayload, BootstrapResult, InstallRequirements } from './api';

const STEP_LABELS = ['Requisitos', 'Organizacion', 'Administrador', 'Correo', 'Almacenamiento', 'Backups', 'Confirmar'] as const;
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
      .catch(() => setRequirementsError('No fue posible verificar los requisitos del servidor.'));
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
      setError(reason instanceof Error ? reason.message : 'No fue posible completar la instalacion.');
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) return <div className="auth-page"><p>Verificando estado de instalacion...</p></div>;

  if (result) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <BrandLogo />
          <h1>Instalacion completa</h1>
          <p>La organizacion, el proyecto y el usuario administrador quedaron creados.</p>
          <ul className="wizard-summary">
            <li><strong>Correo</strong> {result.mail_profile_id ? 'Configurado' : 'Pendiente (configurar en /admin/mail-profiles)'}</li>
            <li><strong>Almacenamiento</strong> {result.storage_profile_id ? 'Perfil local creado' : 'Pendiente (configurar en /admin/storage)'}</li>
            <li><strong>Backups</strong> {result.scheduled_task_id ? 'Respaldo automatico activado' : 'Pendiente (configurar en /admin/backups)'}</li>
          </ul>
          <a href="/">Ir a iniciar sesion</a>
        </div>
      </div>
    );
  }

  if (installed) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <BrandLogo />
          <h1>El sistema ya esta instalado</h1>
          <p>Este instalador solo esta disponible en el primer arranque.</p>
          <a href="/">Ir a iniciar sesion</a>
        </div>
      </div>
    );
  }

  return (
    <div className="auth-page">
      <div className="auth-card wizard-card">
        <BrandLogo />
        <h1>Instalacion inicial</h1>
        <ul className="wizard-steps">
          {STEP_LABELS.map((label, index) => (
            <li key={label} className={index === step ? 'active' : index < step ? 'done' : undefined}>{index + 1}. {label}</li>
          ))}
        </ul>

        {step === 0 ? (
          <fieldset className="wizard-fieldset">
            <p>Verificacion de requisitos minimos del servidor antes de continuar.</p>
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
            ) : !requirementsError ? <p>Verificando...</p> : null}
            <p><small>La conexion a la base de datos se verifica contra la que ya quedo configurada por variable de entorno (DATABASE_URL) al iniciar el servidor; no se puede cambiar desde este asistente sin reiniciar el proceso.</small></p>
          </fieldset>
        ) : null}

        {step === 1 ? (
          <fieldset className="wizard-fieldset">
            <label>Nombre de la organizacion<input required value={form.organization_name} onChange={(event) => updateOrganizationName(event.target.value)} /></label>
            <label>Slug de la organizacion<input required pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" value={form.organization_slug} onChange={(event) => { setSlugTouched(true); updateField('organization_slug', event.target.value); }} /></label>
            <label>URL publica (opcional)<input type="url" placeholder="https://midominio.org" value={form.organization_public_url ?? ''} onChange={(event) => updateField('organization_public_url', event.target.value)} /></label>
          </fieldset>
        ) : null}

        {step === 2 ? (
          <fieldset className="wizard-fieldset">
            <label>Nombre del primer proyecto<input required value={form.project_name} onChange={(event) => updateField('project_name', event.target.value)} /></label>
            <label>Nombre completo del administrador<input required value={form.admin_full_name} onChange={(event) => updateField('admin_full_name', event.target.value)} /></label>
            <label>Documento del administrador<input required value={form.admin_document_id} onChange={(event) => updateField('admin_document_id', event.target.value)} /></label>
            <label>Correo del administrador<input type="email" required value={form.admin_email} onChange={(event) => updateField('admin_email', event.target.value)} /></label>
            <label>Contrasena del administrador<input type="password" required minLength={10} value={form.admin_password} onChange={(event) => updateField('admin_password', event.target.value)} /></label>
          </fieldset>
        ) : null}

        {step === 3 ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={mailEnabled} onChange={(event) => setMailEnabled(event.target.checked)} /> Configurar correo ahora</label>
            {mailEnabled ? (
              <>
                <label>Correo remitente<input type="email" required={mailEnabled} value={mailSenderEmail} onChange={(event) => setMailSenderEmail(event.target.value)} /></label>
                <label>Servidor SMTP (opcional)<input value={mailHost} onChange={(event) => setMailHost(event.target.value)} /></label>
                <label>Puerto SMTP (opcional)<input value={mailPort} onChange={(event) => setMailPort(event.target.value)} /></label>
              </>
            ) : <p><small>Puedes configurarlo despues en /admin/mail-profiles.</small></p>}
          </fieldset>
        ) : null}

        {step === 4 ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={storageEnabled} onChange={(event) => setStorageEnabled(event.target.checked)} /> Crear perfil de almacenamiento local</label>
            {storageEnabled ? (
              <label>Tamano maximo de archivo (MB)<input type="number" min={1} max={1000} value={storageMaxFileSizeMb} onChange={(event) => setStorageMaxFileSizeMb(Number(event.target.value) || 25)} /></label>
            ) : null}
            <p><small>Conectores en la nube (S3/MinIO/Google Drive) se agregan despues en /admin/storage.</small></p>
          </fieldset>
        ) : null}

        {step === 5 ? (
          <fieldset className="wizard-fieldset">
            <label className="wizard-toggle-row"><input type="checkbox" checked={backupEnabled} onChange={(event) => setBackupEnabled(event.target.checked)} /> Activar respaldo automatico</label>
            {backupEnabled ? (
              <label>Frecuencia
                <select value={backupFrequency} onChange={(event) => setBackupFrequency(event.target.value as typeof backupFrequency)}>
                  <option value="hourly">Cada hora</option>
                  <option value="daily">Diario</option>
                  <option value="weekly">Semanal</option>
                </select>
              </label>
            ) : <p><small>Puedes activarlo despues en /admin/backups.</small></p>}
          </fieldset>
        ) : null}

        {step === 6 ? (
          <fieldset className="wizard-fieldset">
            <p>Revisa antes de instalar:</p>
            <ul className="wizard-summary">
              <li><strong>Organizacion</strong> {form.organization_name} ({form.organization_slug})</li>
              <li><strong>Proyecto</strong> {form.project_name}</li>
              <li><strong>Administrador</strong> {form.admin_full_name} ({form.admin_email})</li>
              <li><strong>Correo</strong> {mailEnabled ? mailSenderEmail : 'Sin configurar aun'}</li>
              <li><strong>Almacenamiento</strong> {storageEnabled ? `Local, ${storageMaxFileSizeMb} MB max.` : 'Sin configurar aun'}</li>
              <li><strong>Backups</strong> {backupEnabled ? `Automatico (${backupFrequency})` : 'Sin configurar aun'}</li>
            </ul>
          </fieldset>
        ) : null}

        {error ? <p role="alert">{error}</p> : null}

        <div className="wizard-actions">
          <button type="button" className="secondary" disabled={step === 0} onClick={goBack}>Atras</button>
          {step < 6 ? (
            <button type="button" onClick={goNext}>Siguiente</button>
          ) : (
            <button type="button" disabled={submitting} onClick={() => void submit()}>{submitting ? 'Instalando...' : 'Completar instalacion'}</button>
          )}
        </div>
      </div>
    </div>
  );
}
