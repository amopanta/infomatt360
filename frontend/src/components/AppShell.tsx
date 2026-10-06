import { BrandLogo } from './BrandLogo';
import { Icon } from './Icon';
import { OfflineSyncStatus } from './OfflineSyncStatus';
import { clearStoredSession, currentProjectPermissions, currentSessionProjects, PROJECT_KEY, storeSelectedProjectPermissions } from '../modules/auth/session';
import { logout } from '../modules/auth/api';
import { navigateTo } from '../routeConfig';
import { useEffect, useState } from 'react';
import { fetchMyProjectAssignmentCounts } from '../modules/builder/myFormsApi';

type MenuItem = {
  label: string;
  href: string;
  icon: string;
  permissions?: string[];
  /** Marca el item que despliega el submenu de Formularios. */
  formsSubmenu?: boolean;
};

type MenuGroup = {
  label: string;
  icon: string;
  items: MenuItem[];
};

// Navegacion agrupada. El orden y los permisos se conservan del menu plano
// anterior; el filtrado por permiso sigue vivo (un grupo se oculta si no le
// queda ningun item visible). Reagrupar es solo presentacion: mismos href.
const MENU: MenuGroup[] = [
  {
    label: 'Operación',
    icon: 'gOper',
    items: [
      { label: 'Panel', href: '/', icon: 'dash' },
      { label: 'Mis formularios', href: '/my-forms', icon: 'form', permissions: ['records.write'] },
      { label: 'Formularios', href: '/builder', icon: 'form', permissions: ['builder.write'], formsSubmenu: true },
      { label: 'Actas', href: '/acta', icon: 'acta', permissions: ['builder.write'] },
      { label: 'Participantes', href: '/participants', icon: 'users' },
      { label: 'Equipos de gestores', href: '/teams', icon: 'users', permissions: ['identity.users.manage'] },
      { label: 'Registros', href: '/records', icon: 'records' },
      { label: 'Evidencias', href: '/evidence', icon: 'photo' },
      { label: 'Mapas', href: '/maps', icon: 'map' },
    ],
  },
  {
    label: 'Revisión',
    icon: 'gRev',
    items: [
      { label: 'Flujos de aprobación', href: '/admin/approval-flows', icon: 'check', permissions: ['records.approve'] },
      { label: 'Mensajes', href: '/messages', icon: 'msg' },
      { label: 'Auditoría', href: '/audit', icon: 'shield' },
      { label: 'Auditoría IA', href: '/admin/ai-audit', icon: 'aiaudit', permissions: ['ai.audit.manage'] },
      { label: 'Reportes', href: '/reports', icon: 'report' },
      { label: 'Métricas', href: '/admin/metrics', icon: 'metric', permissions: ['identity.users.manage', 'integrations.api_keys.manage', 'records.approve', 'records.write'] },
    ],
  },
  {
    label: 'Datos e integraciones',
    icon: 'gData',
    items: [
      { label: 'Carga masiva Excel', href: '/admin/excel-import', icon: 'data', permissions: ['identity.users.manage'] },
      { label: 'Importar/Exportar XLSForm', href: '/admin/xlsform', icon: 'exchange', permissions: ['builder.write'] },
      { label: 'Donantes', href: '/admin/donor-sync', icon: 'plug', permissions: ['integrations.donor_sync.manage'] },
      { label: 'API keys', href: '/admin/api-keys', icon: 'key', permissions: ['integrations.api_keys.manage'] },
      { label: 'Sincronización', href: '/admin/bulk-jobs', icon: 'sync', permissions: ['integrations.api_keys.manage', 'records.write'] },
      { label: 'Almacenamiento', href: '/admin/storage', icon: 'box', permissions: ['storage.manage'] },
      { label: 'ERP', href: '/admin/erp', icon: 'erp', permissions: ['erp.manage'] },
      { label: 'Formularios abiertos', href: '/admin/public-links', icon: 'link', permissions: ['builder.write'] },
    ],
  },
  {
    label: 'Administración',
    icon: 'gAdmin',
    items: [
      { label: 'Usuarios', href: '/admin/users', icon: 'users', permissions: ['identity.users.manage'] },
      { label: 'Gobernanza', href: '/admin/governance', icon: 'gov', permissions: ['organizations.tenant_clean', 'identity.users.manage', 'support.tickets.manage'] },
      { label: 'Marca', href: '/admin/branding', icon: 'brand', permissions: ['organizations.branding.manage', 'organizations.manage'] },
      { label: 'Correo', href: '/admin/mail-profiles', icon: 'mail', permissions: ['messages.write'] },
      { label: 'WhatsApp', href: '/admin/whatsapp', icon: 'msg', permissions: ['messages.read', 'records.review', 'records.approve'] },
      { label: 'Backups', href: '/admin/backups', icon: 'backup', permissions: ['backups.manage'] },
      { label: 'Mi seguridad', href: '/account/security', icon: 'lock' },
    ],
  },
];

type Props = {
  title: string;
  children: React.ReactNode;
};

export function AppShell({ title, children }: Props) {
  const projects = currentSessionProjects();
  const selectedProjectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const permissions = currentProjectPermissions();
  const currentPath = window.location.pathname;
  const [projectCounts, setProjectCounts] = useState<Record<string, number>>({});
  useEffect(() => { if (projects.length > 1) void fetchMyProjectAssignmentCounts().then(setProjectCounts).catch(() => undefined); }, [selectedProjectId]);

  function canSee(item: MenuItem) {
    return !item.permissions || item.permissions.some((permission) => permissions.has(permission));
  }

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

  // Solo grupos con al menos un item visible por permiso.
  const visibleGroups = MENU
    .map((group) => ({ ...group, items: group.items.filter(canSee) }))
    .filter((group) => group.items.length > 0);

  function renderItem(item: MenuItem) {
    if (item.formsSubmenu) {
      return (
        <details key={item.label} className="app-nav-group" open={currentPath.startsWith('/builder')}>
          <summary><Icon name={item.icon} /><span>Formularios</span></summary>
          <div className="app-nav-submenu">
            <a href="/builder" className={currentPath === '/builder' ? 'active' : undefined}>Todos los formularios</a>
            <a href="/builder/drafts" className={currentPath === '/builder/drafts' || currentPath === '/builder/new' ? 'active' : undefined}>En construcción</a>
            <a href="/builder/active" className={currentPath === '/builder/active' ? 'active' : undefined}>Formularios activos</a>
            <a href="/builder/archived" className={currentPath === '/builder/archived' ? 'active' : undefined}>Formularios archivados</a>
            <a href="/builder/pull" className={currentPath === '/builder/pull' ? 'active' : undefined}>Grupos Pull</a>
          </div>
        </details>
      );
    }
    const active = isActiveMenuItem(item.href);
    return (
      <a key={item.label} href={item.href} className={active ? 'active' : undefined} aria-current={active ? 'page' : undefined}>
        <Icon name={item.icon} /><span>{item.label}</span>
      </a>
    );
  }

  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <BrandLogo />
        <nav className="app-nav">
          {visibleGroups.map((group) => {
            const hasActive = group.items.some((item) => item.formsSubmenu ? currentPath.startsWith('/builder') : isActiveMenuItem(item.href));
            return (
              <details key={group.label} className="app-nav-section" open={hasActive || group.label === 'Operación'}>
                <summary>
                  <Icon name={group.icon} className="app-nav-section-icon" />
                  <span>{group.label}</span>
                  <Icon name="chevron" className="app-nav-caret" />
                </summary>
                <div className="app-nav-section-items">
                  {group.items.map(renderItem)}
                </div>
              </details>
            );
          })}
        </nav>
        <small>InfoMatt360</small>
      </aside>
      <section className="app-main">
        <header className="app-header">
          <h1>{title}</h1>
          <div className="app-header-actions">
            {projects.length > 1 ? (
              <label>
                Proyecto
                <select value={selectedProjectId} onChange={(event) => changeProject(event.target.value)}>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}{projectCounts[project.id] ? ` · ${projectCounts[project.id]} asignados` : ''}</option>)}
                </select>
              </label>
            ) : projects[0] ? <span>{projects[0].name}</span> : null}
            <OfflineSyncStatus />
            <button className="app-logout" onClick={() => void closeSession()}>Cerrar sesión</button>
          </div>
        </header>
        {children}
      </section>
    </div>
  );
}

