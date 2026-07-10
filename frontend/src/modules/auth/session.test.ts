import { beforeEach, describe, expect, it, vi } from 'vitest';

import { authorizationHeader, clearStoredSession, currentAccessToken, currentProjectPermissions, currentSessionProjects, hasAnyCurrentProjectPermission, PROJECT_KEY, PROJECT_PERMISSIONS_KEY, PROJECTS_KEY, REFRESH_TOKEN_KEY, setAccessToken, storeSelectedProjectPermissions, storeSessionProjects, TOKEN_KEY, validSelectedProject } from './session';

const projects = [{ id: 'p1', name: 'Uno', permissions: ['records.read'] }, { id: 'p2', name: 'Dos', permissions: ['records.write', 'records.approve'] }];

function installLocalStorageMock() {
  const values = new Map<string, string>();
  vi.stubGlobal('localStorage', {
    getItem: (key: string) => values.get(key) ?? null,
    setItem: (key: string, value: string) => { values.set(key, value); },
    removeItem: (key: string) => { values.delete(key); },
  });
}

describe('validSelectedProject', () => {
  it('conserva solo una seleccion autorizada', () => {
    expect(validSelectedProject(projects, 'p2')).toBe('p2');
    expect(validSelectedProject(projects, 'externo')).toBeNull();
  });

  it('selecciona automaticamente el unico proyecto disponible', () => {
    expect(validSelectedProject([projects[0]], null)).toBe('p1');
  });
});

describe('project permissions storage', () => {
  beforeEach(() => {
    installLocalStorageMock();
    clearStoredSession();
  });

  it('guarda permisos del proyecto seleccionado', () => {
    storeSelectedProjectPermissions(projects, 'p2');

    expect(JSON.parse(localStorage.getItem(PROJECT_PERMISSIONS_KEY) ?? '[]')).toEqual(['records.write', 'records.approve']);
    expect(currentProjectPermissions().has('records.approve')).toBe(true);
    expect(currentProjectPermissions().has('records.read')).toBe(false);
    expect(hasAnyCurrentProjectPermission(['records.read', 'records.approve'])).toBe(true);
    expect(hasAnyCurrentProjectPermission(['identity.users.manage'])).toBe(false);
  });

  it('limpia permisos si el proyecto no existe', () => {
    storeSelectedProjectPermissions(projects, 'externo');

    expect(currentProjectPermissions().size).toBe(0);
  });

  it('guarda y recupera proyectos de la sesion', () => {
    storeSessionProjects(projects);

    expect(JSON.parse(localStorage.getItem(PROJECTS_KEY) ?? '[]')).toHaveLength(2);
    expect(currentSessionProjects().map((project) => project.id)).toEqual(['p1', 'p2']);
  });

  it('recalcula permisos al cambiar de proyecto', () => {
    storeSessionProjects(projects);
    localStorage.setItem(PROJECT_KEY, 'p1');
    storeSelectedProjectPermissions(projects, 'p1');
    expect(hasAnyCurrentProjectPermission(['records.read'])).toBe(true);
    expect(hasAnyCurrentProjectPermission(['records.write'])).toBe(false);

    localStorage.setItem(PROJECT_KEY, 'p2');
    storeSelectedProjectPermissions(currentSessionProjects(), 'p2');
    expect(hasAnyCurrentProjectPermission(['records.read'])).toBe(false);
    expect(hasAnyCurrentProjectPermission(['records.write'])).toBe(true);
  });

  it('limpia token, proyecto y permisos al cerrar sesion', () => {
    setAccessToken('token');
    localStorage.setItem(REFRESH_TOKEN_KEY, 'refresh');
    localStorage.setItem(PROJECT_KEY, 'p1');
    storeSelectedProjectPermissions(projects, 'p1');
    storeSessionProjects(projects);

    clearStoredSession();

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(localStorage.getItem(REFRESH_TOKEN_KEY)).toBeNull();
    expect(currentAccessToken()).toBe('');
    expect(localStorage.getItem(PROJECT_KEY)).toBeNull();
    expect(localStorage.getItem(PROJECT_PERMISSIONS_KEY)).toBeNull();
    expect(localStorage.getItem(PROJECTS_KEY)).toBeNull();
  });

  it('mantiene el access token solo en memoria', () => {
    setAccessToken('access-123');

    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
    expect(currentAccessToken()).toBe('access-123');
    expect(authorizationHeader()).toEqual({ Authorization: 'Bearer access-123' });
  });

  it('migra y borra tokens legacy encontrados en localStorage', () => {
    localStorage.setItem(TOKEN_KEY, 'legacy-token');

    expect(currentAccessToken()).toBe('legacy-token');
    expect(localStorage.getItem(TOKEN_KEY)).toBeNull();
  });
});
