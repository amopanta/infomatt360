import type { SessionProject } from './types';

export const TOKEN_KEY = 'infomatt360_token';
export const REFRESH_TOKEN_KEY = 'infomatt360_refresh_token';
export const PROJECT_KEY = 'infomatt360_project_id';
export const PROJECT_PERMISSIONS_KEY = 'infomatt360_project_permissions';
export const PROJECTS_KEY = 'infomatt360_projects';

let accessTokenInMemory: string | null = null;

export function setAccessToken(token: string): void {
  accessTokenInMemory = token;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

export function currentAccessToken(): string {
  if (accessTokenInMemory) return accessTokenInMemory;
  const legacyToken = localStorage.getItem(TOKEN_KEY);
  if (legacyToken) {
    accessTokenInMemory = legacyToken;
    localStorage.removeItem(TOKEN_KEY);
  }
  return accessTokenInMemory ?? '';
}

export function authorizationHeader(): HeadersInit {
  const token = currentAccessToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function jsonAuthHeaders(): HeadersInit {
  return { 'Content-Type': 'application/json', ...authorizationHeader() };
}

export function validSelectedProject(projects: SessionProject[], selectedProjectId: string | null): string | null {
  if (selectedProjectId && projects.some((project) => project.id === selectedProjectId)) return selectedProjectId;
  return projects.length === 1 ? projects[0].id : null;
}

export function storeSelectedProjectPermissions(projects: SessionProject[], selectedProjectId: string | null): void {
  const project = projects.find((item) => item.id === selectedProjectId);
  localStorage.setItem(PROJECT_PERMISSIONS_KEY, JSON.stringify(project?.permissions ?? []));
}

export function storeSessionProjects(projects: SessionProject[]): void {
  localStorage.setItem(PROJECTS_KEY, JSON.stringify(projects));
}

export function currentSessionProjects(): SessionProject[] {
  try {
    const parsed = JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? '[]');
    if (!Array.isArray(parsed)) return [];
    return parsed.filter((project) => typeof project?.id === 'string' && typeof project?.name === 'string') as SessionProject[];
  } catch {
    return [];
  }
}

export function currentProjectPermissions(): Set<string> {
  try {
    const parsed = JSON.parse(localStorage.getItem(PROJECT_PERMISSIONS_KEY) ?? '[]');
    return new Set(Array.isArray(parsed) ? parsed.filter((item) => typeof item === 'string') : []);
  } catch {
    return new Set();
  }
}

export function hasAnyCurrentProjectPermission(requiredPermissions: string[]): boolean {
  const permissions = currentProjectPermissions();
  return requiredPermissions.some((permission) => permissions.has(permission));
}

export function clearStoredSession(): void {
  accessTokenInMemory = null;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(PROJECT_KEY);
  localStorage.removeItem(PROJECT_PERMISSIONS_KEY);
  localStorage.removeItem(PROJECTS_KEY);
}
