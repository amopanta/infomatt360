import { BrandLogo } from './BrandLogo';
import { clearStoredSession, currentProjectPermissions, currentSessionProjects, PROJECT_KEY, storeSelectedProjectPermissions } from '../modules/auth/session';
import { logout } from '../modules/auth/api';
import { navigateTo } from '../routeConfig';

const menu = [
  { label: 'Dashboard', href: '/' },
  { label: 'Formularios', href: '/builder', permissions: ['builder.write'] },
  { label: 'Registros', href: '/records' },
  { label: 'Reportes', href: '/reports' },
  { label: 'Mapas', href: '/maps' },
  { label: 'Mensajes', href: '/messages' },
  { label: 'Auditoria', href: '/audit' },
  { label: 'Usuarios', href: '/admin/users', permissions: ['identity.users.manage'] },
  { label: 'Flujos de aprobacion', href: '/admin/approval-flows', permissions: ['records.approve'] },
  { label: 'API keys', href: '/admin/api-keys', permissions: ['integrations.api_keys.manage'] },
  { label: 'Sincronizacion', href: '/admin/bulk-jobs', permissions: ['integrations.api_keys.manage', 'records.write'] },
  { label: 'Metricas', href: '/admin/metrics', permissions: ['identity.users.manage', 'integrations.api_keys.manage', 'records.approve', 'records.write'] },
  { label: 'Mi seguridad', href: '/account/security' },
];

type Props = {
  title: string;
  children: React.ReactNode;
};

export function AppShell({ title, children }: Props) {
  const projects = currentSessionProjects();
  const selectedProjectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const permissions = currentProjectPermissions();
  const visibleMenu = menu.filter((item) => !item.permissions || item.permissions.some((permission) => permissions.has(permission)));
  const currentPath = window.location.pathname;

  function isActiveMenuItem(href: string) {
    if (href === '/') return currentPath === '/';
    return currentPath === href || currentPath.startsWith(`${href}/`);
  }

  function changeProject(projectId: string) {
    localStorage.setItem(PROJECT_KEY, projectId);
    storeSelectedProjectPermissions(projects, projectId);
    navigateTo('/');
  }

  async function closeSession() {
    try {
      await logout();
    } finally {
      clearStoredSession();
      window.location.reload();
    }
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <BrandLogo />
        <nav>
          {visibleMenu.map((item) => (
            <a key={item.label} href={item.href} className={isActiveMenuItem(item.href) ? 'active' : undefined} aria-current={isActiveMenuItem(item.href) ? 'page' : undefined}>{item.label}</a>
          ))}
        </nav>
        <small>InfoMatt360 · v0.1</small>
      </aside>
      <section className="app-main">
        <header className="app-header">
          <h1>{title}</h1>
          <div className="app-header-actions">
            {projects.length > 1 ? (
              <label>
                Proyecto
                <select value={selectedProjectId} onChange={(event) => changeProject(event.target.value)}>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}</option>)}
                </select>
              </label>
            ) : projects[0] ? <span>{projects[0].name}</span> : null}
            <button className="app-logout" onClick={() => void closeSession()}>Cerrar sesion</button>
          </div>
        </header>
        {children}
      </section>
    </div>
  );
}
