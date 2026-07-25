import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type Organization = {
  id: string;
  name: string;
  slug: string;
  status: string;
};

export type OrganizationBranding = {
  organization_id: string;
  logo_url?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
  background_color?: string | null;
  slogan?: string | null;
};

export type AdminProject = {
  id: string;
  name: string;
  description?: string | null;
  status: string;
  organization_id?: string | null;
};

function headers(): HeadersInit {
  return { ...authorizationHeader(), 'Content-Type': 'application/json' };
}

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function fetchOrganizations(): Promise<Organization[]> {
  const response = await fetch(`${API_BASE_URL}/organizations/`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar las organizaciones.');
}

export async function fetchOrganizationBranding(organizationId: string): Promise<OrganizationBranding | null> {
  const response = await fetch(`${API_BASE_URL}/organizations/${organizationId}/branding`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar la marca de la organizacion.');
}

export type BrandingSavePayload = {
  logo_url?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
  background_color?: string | null;
  slogan?: string | null;
};

export async function saveOrganizationBranding(organizationId: string, payload: BrandingSavePayload): Promise<OrganizationBranding> {
  const response = await fetch(`${API_BASE_URL}/organizations/${organizationId}/branding`, {
    method: 'PUT',
    headers: headers(),
    body: JSON.stringify(payload),
  });
  return parseOrThrow(response, 'No fue posible guardar la marca de la organizacion.');
}

export async function uploadOrganizationLogo(organizationId: string, file: File): Promise<OrganizationBranding> {
  const formData = new FormData();
  formData.append('upload', file);
  // Sin Content-Type manual: el navegador define el boundary del multipart.
  const response = await fetch(`${API_BASE_URL}/organizations/${organizationId}/branding/logo`, {
    method: 'POST',
    headers: { ...authorizationHeader() },
    body: formData,
  });
  return parseOrThrow(response, 'No fue posible subir el logo.');
}

export async function fetchAdminProjects(): Promise<AdminProject[]> {
  const response = await fetch(`${API_BASE_URL}/identity/projects`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los proyectos.');
}

export async function setProjectOrganization(projectId: string, organizationId: string | null): Promise<AdminProject> {
  const response = await fetch(`${API_BASE_URL}/identity/projects/${projectId}`, {
    method: 'PATCH',
    headers: headers(),
    body: JSON.stringify({ organization_id: organizationId }),
  });
  return parseOrThrow(response, 'No fue posible actualizar la organizacion del proyecto.');
}
