import { useEffect, useRef, useState } from 'react';

import { AppShell } from '../../components/AppShell';
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
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [projects, setProjects] = useState<AdminProject[]>([]);
  const [selectedOrgId, setSelectedOrgId] = useState('');
  const [branding, setBranding] = useState<OrganizationBranding | null>(null);
  const [message, setMessage] = useState('');

  const [primaryColor, setPrimaryColor] = useState('');
  const [accentColor, setAccentColor] = useState('');
  const [backgroundColor, setBackgroundColor] = useState('');
  const [slogan, setSlogan] = useState('');
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
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar las organizaciones.');
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
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar la marca.');
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
      setMessage('Logo subido correctamente.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible subir el logo.');
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
      // Se reenvia el logo_url vigente a proposito: PUT /branding pisa todos
      // los campos, y omitirlo borraria el logo ya subido.
      const updated = await saveOrganizationBranding(selectedOrgId, {
        logo_url: branding?.logo_url ?? null,
        primary_color: primaryColor.trim() || null,
        accent_color: accentColor.trim() || null,
        background_color: backgroundColor.trim() || null,
        slogan: slogan.trim() || null,
      });
      setBranding(updated);
      setMessage('Marca guardada correctamente.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible guardar la marca.');
    } finally {
      setSaving(false);
    }
  }

  async function submitLinkProject(project: AdminProject, organizationId: string | null) {
    setLinkingProjectId(project.id);
    setMessage('');
    try {
      await setProjectOrganization(project.id, organizationId);
      setMessage(organizationId ? `Proyecto "${project.name}" vinculado a la organizacion.` : `Proyecto "${project.name}" desvinculado.`);
      await loadProjects();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el proyecto.');
    } finally {
      setLinkingProjectId(null);
    }
  }

  const selectedOrg = organizations.find((org) => org.id === selectedOrgId) ?? null;

  return (
    <AppShell title="Marca de la organizacion">
      {message ? <p className="feedback">{message}</p> : null}

      <section className="panel">
        <header>
          <h2>Organizacion</h2>
          <p>El logo y los colores aparecen en la pantalla de inicio de sesion y en las actas PDF de los proyectos vinculados.</p>
        </header>
        <label>
          Organizacion
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
              <h2>Logo</h2>
              <p>PNG, JPEG o WebP, maximo 2MB. Reemplaza el anterior al subir uno nuevo.</p>
            </header>
            {branding?.logo_url ? (
              <p><img src={branding.logo_url} alt={`Logo de ${selectedOrg.name}`} style={{ maxHeight: 80 }} /></p>
            ) : (
              <p><small>Esta organizacion todavia no tiene logo cargado.</small></p>
            )}
            <label>
              Subir logo
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
            {uploading ? <p><small>Subiendo logo...</small></p> : null}
          </section>

          <section className="panel">
            <header>
              <h2>Colores y eslogan</h2>
            </header>
            <form onSubmit={submitBranding}>
              <label>
                Color primario (hex)
                <input value={primaryColor} onChange={(event) => setPrimaryColor(event.target.value)} placeholder="#0A2540" />
              </label>
              <label>
                Color de acento (hex)
                <input value={accentColor} onChange={(event) => setAccentColor(event.target.value)} placeholder="#38BDF8" />
              </label>
              <label>
                Color de fondo (hex)
                <input value={backgroundColor} onChange={(event) => setBackgroundColor(event.target.value)} placeholder="#F8FAFC" />
              </label>
              <label>
                Eslogan
                <input value={slogan} onChange={(event) => setSlogan(event.target.value)} placeholder="Territorio conectado" />
              </label>
              <button type="submit" disabled={saving}>{saving ? 'Guardando...' : 'Guardar marca'}</button>
            </form>
          </section>

          <section className="panel">
            <header>
              <h2>Proyectos vinculados</h2>
              <p>Las actas de un proyecto usan el logo de su organizacion. Un proyecto sin organizacion genera actas sin logo.</p>
            </header>
            <table className="records-table">
              <thead>
                <tr>
                  <th>Proyecto</th>
                  <th>Organizacion actual</th>
                  <th>Accion</th>
                </tr>
              </thead>
              <tbody>
                {projects.map((project) => {
                  const linkedHere = project.organization_id === selectedOrgId;
                  const linkedName = organizations.find((org) => org.id === project.organization_id)?.name;
                  return (
                    <tr key={project.id}>
                      <td>{project.name}</td>
                      <td>{project.organization_id ? (linkedName ?? project.organization_id) : 'Sin organizacion'}</td>
                      <td>
                        {linkedHere ? (
                          <button type="button" disabled={linkingProjectId === project.id} onClick={() => void submitLinkProject(project, null)}>
                            {linkingProjectId === project.id ? 'Actualizando...' : 'Desvincular'}
                          </button>
                        ) : (
                          <button type="button" disabled={linkingProjectId === project.id} onClick={() => void submitLinkProject(project, selectedOrgId)}>
                            {linkingProjectId === project.id ? 'Actualizando...' : `Vincular a ${selectedOrg.name}`}
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
          <p>No hay organizaciones registradas. Crea una desde la API de organizaciones o el instalador.</p>
        </section>
      )}
    </AppShell>
  );
}
