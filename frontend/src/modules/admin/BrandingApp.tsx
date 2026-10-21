import { useEffect, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import {
  fetchAdminProjects,
  fetchOrganizationBranding,
  fetchOrganizations,
  saveOrganizationBranding,
  setProjectOrganization,
  uploadOrganizationLogo,
} from './brandingAdminApi';
import type { AdminProject, Organization, OrganizationBranding } from './brandingAdminApi';

export function BrandingApp() {
  const { t } = useI18n();
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [projects, setProjects] = useState<AdminProject[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState('');
  const [branding, setBranding] = useState<OrganizationBranding | null>(null);
  const [message, setMessage] = useState('');

  const [primaryColor, setPrimaryColor] = useState('');
  const [accentColor, setAccentColor] = useState('');
  const [backgroundColor, setBackgroundColor] = useState('');
  const [slogan, setSlogan] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [saving, setSaving] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [linkingProjectId, setLinkingProjectId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  async function loadOrganizations() {
    try {
      const rows = await fetchOrganizations();
      setOrganizations(rows);
      if (rows.length > 0 && !selectedOrgId) setSelectedOrgId(rows[0].id);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.branding.errorLoadOrganizations'));
    }
  }

  async function loadProjects() {
    try {
      setProjects(await fetchAdminProjects());
    } catch {
      setProjects([]);
    }
  }

  async function loadBranding(organizationId: string) {
    try {
      const row = await fetchOrganizationBranding(organizationId);
      setBranding(row);
      setPrimaryColor(row?.primary_color ?? '');
      setAccentColor(row?.accent_color ?? '');
      setBackgroundColor(row?.background_color ?? '');
      setSlogan(row?.slogan ?? '');
      setCompanyName(row?.organization_name ?? organizations.find((org) => org.id === organizationId)?.name ?? '');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.branding.errorLoadBranding'));
    }
  }

  useEffect(() => { void loadOrganizations(); void loadProjects(); }, []);
  useEffect(() => { if (selectedOrgId) void loadBranding(selectedOrgId); }, [selectedOrgId]);

  async function submitLogo(file: File) {
    setUploading(true);
    setMessage('');
    try {
      const updated = await uploadOrganizationLogo(selectedOrgId, file);
      setBranding(updated);
      setMessage(t('admin.branding.logoUploaded'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.branding.errorUploadLogo'));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  }

  async function submitBranding(event: React.FormEvent) {
    event.preventDefault();
    setSaving(true);
    setMessage('');
    try {
      const updated = await saveOrganizationBranding(selectedOrgId, {
        logo_url: branding?.logo_url ?? null,
        primary_color: primaryColor.trim() || null,
        accent_color: accentColor.trim() || null,
        background_color: backgroundColor.trim() || null,
        slogan: slogan.trim() || null,
        organization_name: companyName.trim() || null,
      });
      setBranding(updated);
      // El nombre también se ve en el selector de organizaciones.
      if (updated.organization_name) setOrganizations((current) => current.map((org) => org.id === selectedOrgId ? { ...org, name: updated.organization_name! } : org));
      setMessage(t('admin.branding.brandingSaved'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.branding.errorSaveBranding'));
    } finally {
      setSaving(false);
    }
  }

  async function submitLinkProject(project: AdminProject, organizationId: string | null) {
    setLinkingProjectId(project.id);
    setMessage('');
    try {
      await setProjectOrganization(project.id, organizationId);
      setMessage(organizationId ? t('admin.branding.projectLinked', { name: project.name }) : t('admin.branding.projectUnlinked', { name: project.name }));
      await loadProjects();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.branding.errorUpdateProject'));
    } finally {
      setLinkingProjectId(null);
    }
  }

  const selectedOrg = organizations.find((org) => org.id === selectedOrgId) ?? null;

  return (
    <AppShell title={t('admin.branding.title')}>
      {message ? <p className="feedback">{message}</p> : null}

      <section className="panel">
        <header>
          <h2>{t('admin.branding.organizationTitle')}</h2>
          <p>{t('admin.branding.organizationDescription')}</p>
        </header>
        <label>
          {t('admin.branding.organizationLabel')}
          <select value={selectedOrgId} onChange={(event) => setSelectedOrgId(event.target.value)}>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>{org.name} ({org.slug})</option>
            ))}
          </select>
        </label>
      </section>

      {selectedOrg ? (
        <>
          <section className="panel">
            <header>
              <h2>{t('admin.branding.logoTitle')}</h2>
              <p>{t('admin.branding.logoDescription')}</p>
            </header>
            {branding?.logo_url ? (
              <p><img src={branding.logo_url} alt={t('admin.branding.logoAlt', { name: selectedOrg.name })} style={{ maxHeight: 80 }} /></p>
            ) : (
              <p><small>{t('admin.branding.noLogoYet')}</small></p>
            )}
            <label>
              {t('admin.branding.uploadLogo')}
              <input
                ref={fileInputRef}
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={uploading}
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void submitLogo(file);
                }}
              />
            </label>
            {uploading ? <p><small>{t('admin.branding.uploadingLogo')}</small></p> : null}
          </section>

          <section className="panel">
            <header>
              <h2>{t('admin.branding.colorsAndSlogan')}</h2>
            </header>
            <form onSubmit={submitBranding}>
              <label>
                {t('ux.branding.companyName')}
                <input value={companyName} minLength={2} maxLength={180} onChange={(event) => setCompanyName(event.target.value)} />
                <small>{t('ux.branding.companyNameHint')}</small>
              </label>
              <label>
                {t('admin.branding.primaryColorLabel')}
                <input value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} placeholder="#0A2540" />
              </label>
              <label>
                {t('admin.branding.accentColorLabel')}
                <input value={accentColor} onChange={(event) => setAccentColor(event.target.value)} placeholder="#38BDF8" />
              </label>
              <label>
                {t('admin.branding.backgroundColorLabel')}
                <input value={backgroundColor} onChange={(event) => setBackgroundColor(event.target.value)} placeholder="#F8FAFC" />
              </label>
              <label>
                {t('admin.branding.sloganLabel')}
                <input value={slogan} onChange={(event) => setSlogan(event.target.value)} placeholder={t('admin.branding.sloganPlaceholder')} />
              </label>
              <button type="submit" disabled={saving}>{saving ? t('admin.branding.saving') : t('admin.branding.saveBranding')}</button>
            </form>
          </section>

          <section className="panel">
            <header>
              <h2>{t('admin.branding.linkedProjects')}</h2>
              <p>{t('admin.branding.linkedProjectsDescription')}</p>
            </header>
            <table className="records-table">
              <thead>
                <tr>
                  <th>{t('admin.branding.colProject')}</th>
                  <th>{t('admin.branding.colCurrentOrg')}</th>
                  <th>{t('admin.branding.colAction')}</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => {
                  const linkedHere = project.organization_id === selectedOrgId;
                  const linkedName = organizations.find((org) => org.id === project.organization_id)?.name;
                  return (
                    <tr key={project.id}>
                      <td>{project.name}</td>
                      <td>{project.organization_id ? (linkedName ?? project.organization_id) : t('admin.branding.noOrganization')}</td>
                      <td>
                        {linkedHere ? (
                          <button type="button" disabled={linkingProjectId === project.id} onClick={() => void submitLinkProject(project, null)}>
                            {linkingProjectId === project.id ? t('admin.branding.updating') : t('admin.branding.unlink')}
                          </button>
                        ) : (
                          <button type="button" disabled={linkingProjectId === project.id} onClick={() => void submitLinkProject(project, selectedOrgId)}>
                            {linkingProjectId === project.id ? t('admin.branding.updating') : t('admin.branding.linkTo', { name: selectedOrg.name })}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
        </>
      ) : (
        <section className="panel">
          <p>{t('admin.branding.noOrganizations')}</p>
        </section>
      )}
    </AppShell>
  );
}
