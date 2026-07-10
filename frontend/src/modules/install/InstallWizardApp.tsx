import { useEffect, useState } from 'react';

import { BrandLogo } from '../../components/BrandLogo';
import { bootstrapInstallation, fetchInstallStatus } from './api';
import type { BootstrapPayload } from './api';

const EMPTY_FORM: BootstrapPayload = {
  organization_name: '',
  organization_slug: '',
  project_name: '',
  admin_full_name: '',
  admin_document_id: '',
  admin_email: '',
  admin_password: '',
};

export function InstallWizardApp() {
  const [checking, setChecking] = useState(true);
  const [installed, setInstalled] = useState(true);
  const [form, setForm] = useState<BootstrapPayload>(EMPTY_FORM);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [done, setDone] = useState(false);

  useEffect(() => {
    fetchInstallStatus()
      .then((status) => setInstalled(status.installed))
      .catch(() => setInstalled(true))
      .finally(() => setChecking(false));
  }, []);

  function updateField(field: keyof BootstrapPayload, value: string) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setError('');
    setSubmitting(true);
    try {
      await bootstrapInstallation(form);
      setDone(true);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible completar la instalacion.');
    } finally {
      setSubmitting(false);
    }
  }

  if (checking) return <div className="auth-page"><p>Verificando estado de instalacion...</p></div>;

  if (done) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <BrandLogo />
          <h1>Instalacion completa</h1>
          <p>La organizacion, el proyecto y el usuario administrador quedaron creados.</p>
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
      <form className="auth-card" onSubmit={(event) => void submit(event)}>
        <BrandLogo />
        <h1>Instalacion inicial</h1>
        <p>Crea la primera organizacion, el primer proyecto y el usuario administrador.</p>
        <label>Nombre de la organizacion<input required value={form.organization_name} onChange={(event) => updateField('organization_name', event.target.value)} /></label>
        <label>Slug de la organizacion<input required pattern="[a-z0-9][a-z0-9-]*[a-z0-9]" value={form.organization_slug} onChange={(event) => updateField('organization_slug', event.target.value)} /></label>
        <label>Nombre del primer proyecto<input required value={form.project_name} onChange={(event) => updateField('project_name', event.target.value)} /></label>
        <label>Nombre completo del administrador<input required value={form.admin_full_name} onChange={(event) => updateField('admin_full_name', event.target.value)} /></label>
        <label>Documento del administrador<input required value={form.admin_document_id} onChange={(event) => updateField('admin_document_id', event.target.value)} /></label>
        <label>Correo del administrador<input type="email" required value={form.admin_email} onChange={(event) => updateField('admin_email', event.target.value)} /></label>
        <label>Contrasena del administrador<input type="password" required minLength={10} value={form.admin_password} onChange={(event) => updateField('admin_password', event.target.value)} /></label>
        {error ? <p role="alert">{error}</p> : null}
        <button type="submit" disabled={submitting}>{submitting ? 'Instalando...' : 'Completar instalacion'}</button>
      </form>
    </div>
  );
}
