import { BrandLogo } from './BrandLogo';
import { Icon } from './Icon';
import { OfflineSyncStatus } from './OfflineSyncStatus';
import { clearStoredSession, currentProjectPermissions, currentSessionProjects, PROJECT_KEY, storeSelectedProjectPermissions } from '../modules/auth/session';
import { logout } from '../modules/auth/api';
import { navigateTo } from '../routeConfig';
import { useEffect, useState } from 'react';
import { fetchMyProjectAssignmentCounts } from '../modules/builder/myFormsApi';
import { useI18n, LanguageSelector } from '../i18n';

type MenuItem = {
  labelKey: string;
  href: string;
  icon: string;
  permissions?: string[];
  formsSubmenu?: boolean;
};

type MenuGroup = {
  labelKey: string;
  icon: string;
  items: MenuItem[];
};

// Menu organizado por lo que la persona quiere hacer (no por modulo tecnico):
// Inicio → Formularios → Datos → Revision → Configuracion → Avanzado.
// Cada opcion se filtra por permisos, asi un encuestador de campo solo ve
// Inicio, Datos y su seguridad; lo tecnico queda en "Avanzado" (cerrado).
const MENU: MenuGroup[] = [
  {
    labelKey: 'ux.nav.home',
    icon: 'gOper',
    items: [
      { labelKey: 'ux.nav.home', href: '/', icon: 'dash' },
      { labelKey: 'ux.nav.fill', href: '/my-forms', icon: 'form', permissions: ['records.write'] },
    ],
  },
  {
    labelKey: 'ux.nav.forms',
    icon: 'form',
    items: [
      { labelKey: 'ux.nav.createEdit', href: '/builder', icon: 'form', permissions: ['builder.write'], formsSubmenu: true },
      { labelKey: 'nav.actas', href: '/acta', icon: 'acta', permissions: ['builder.write'] },
      { labelKey: 'nav.publicForms', href: '/admin/public-links', icon: 'link', permissions: ['builder.write'] },
      { labelKey: 'ux.nav.xlsform', href: '/admin/xlsform', icon: 'exchange', permissions: ['builder.write'] },
    ],
  },
  {
    labelKey: 'ux.nav.data',
    icon: 'gData',
    items: [
      { labelKey: 'nav.records', href: '/records', icon: 'records' },
      { labelKey: 'nav.participants', href: '/participants', icon: 'users' },
      { labelKey: 'nav.appliedActivities', href: '/activities', icon: 'records' },
      { labelKey: 'nav.evidence', href: '/evidence', icon: 'photo' },
      { labelKey: 'nav.maps', href: '/maps', icon: 'map' },
    ],
  },
  {
    labelKey: 'ux.nav.review',
    icon: 'gRev',
    items: [
      { labelKey: 'ux.nav.fieldDevices', href: '/field-devices', icon: 'tablet', permissions: ['records.review', 'records.coordinate', 'identity.users.manage'] },
      { labelKey: 'nav.approvalFlows', href: '/admin/approval-flows', icon: 'check', permissions: ['records.approve'] },
      { labelKey: 'nav.messages', href: '/messages', icon: 'msg' },
      { labelKey: 'ux.nav.planner', href: '/planner', icon: 'metric', permissions: ['planner.manage', 'identity.users.manage', 'records.review', 'records.approve', 'records.coordinate', 'reports.export', 'records.write'] },
      { labelKey: 'nav.reports', href: '/reports', icon: 'report' },
      { labelKey: 'nav.audit', href: '/audit', icon: 'shield' },
      { labelKey: 'nav.metrics', href: '/admin/metrics', icon: 'metric', permissions: ['identity.users.manage', 'integrations.api_keys.manage', 'records.approve', 'records.write'] },
    ],
  },
  {
    labelKey: 'ux.nav.settings',
    icon: 'gAdmin',
    items: [
      { labelKey: 'nav.users', href: '/admin/users', icon: 'users', permissions: ['identity.users.manage'] },
      { labelKey: 'nav.teams', href: '/teams', icon: 'users', permissions: ['identity.users.manage'] },
      { labelKey: 'nav.branding', href: '/admin/branding', icon: 'brand', permissions: ['organizations.branding.manage', 'organizations.manage'] },
      { labelKey: 'nav.mail', href: '/admin/mail-profiles', icon: 'mail', permissions: ['messages.write'] },
      { labelKey: 'nav.whatsapp', href: '/admin/whatsapp', icon: 'msg', permissions: ['messages.read', 'records.review', 'records.approve'] },
      { labelKey: 'nav.mySecurity', href: '/account/security', icon: 'lock' },
    ],
  },
  {
    labelKey: 'ux.nav.advanced',
    icon: 'plug',
    items: [
      { labelKey: 'nav.excelImport', href: '/admin/excel-import', icon: 'data', permissions: ['identity.users.manage'] },
      { labelKey: 'nav.sync', href: '/admin/bulk-jobs', icon: 'sync', permissions: ['integrations.api_keys.manage', 'records.write'] },
      { labelKey: 'ux.nav.apiKeys', href: '/admin/api-keys', icon: 'key', permissions: ['integrations.api_keys.manage'] },
      { labelKey: 'nav.donors', href: '/admin/donor-sync', icon: 'plug', permissions: ['integrations.donor_sync.manage'] },
      { labelKey: 'nav.erp', href: '/admin/erp', icon: 'erp', permissions: ['erp.manage'] },
      { labelKey: 'nav.storage', href: '/admin/storage', icon: 'box', permissions: ['storage.manage'] },
      { labelKey: 'nav.aiAudit', href: '/admin/ai-audit', icon: 'aiaudit', permissions: ['ai.audit.manage'] },
      { labelKey: 'nav.governance', href: '/admin/governance', icon: 'gov', permissions: ['organizations.tenant_clean', 'identity.users.manage', 'support.tickets.manage'] },
      { labelKey: 'ux.nav.backups', href: '/admin/backups', icon: 'backup', permissions: ['backups.manage'] },
      { labelKey: 'ux.nav.mirror', href: '/admin/mirror', icon: 'db', permissions: ['mirror.manage'] },
    ],
  },
];

type Props = {
  title: string;
  children: React.ReactNode;
};

export function AppShell({ title, children }: Props) {
  const { t } = useI18n();
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

  const visibleGroups = MENU
    .map((group) => ({ ...group, items: group.items.filter(canSee) }))
    .filter((group) => group.items.length > 0);

  function renderItem(item: MenuItem) {
    const label = t(item.labelKey);
    if (item.formsSubmenu) {
      return (
        <details key={item.labelKey} className="app-nav-group" open={currentPath.startsWith('/builder')}>
          <summary><Icon name={item.icon} /><span>{label}</span></summary>
          <div className="app-nav-submenu">
            <a href="/builder" className={currentPath === '/builder' ? 'active' : undefined}>{t('nav.allForms')}</a>
            <a href="/builder/drafts" className={currentPath === '/builder/drafts' || currentPath === '/builder/new' ? 'active' : undefined}>{t('nav.inProgress')}</a>
            <a href="/builder/active" className={currentPath === '/builder/active' ? 'active' : undefined}>{t('nav.activeForms')}</a>
            <a href="/builder/archived" className={currentPath === '/builder/archived' ? 'active' : undefined}>{t('nav.archivedForms')}</a>
            <a href="/builder/pull" className={currentPath === '/builder/pull' ? 'active' : undefined}>{t('ux.nav.pullGroups')}</a>
          </div>
        </details>
      );
    }
    const active = isActiveMenuItem(item.href);
    return (
      <a key={item.labelKey} href={item.href} className={active ? 'active' : undefined} aria-current={active ? 'page' : undefined}>
        <Icon name={item.icon} /><span>{label}</span>
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
              <details key={group.labelKey} className="app-nav-section" open={hasActive || (group.labelKey !== 'ux.nav.advanced' && group.labelKey !== 'ux.nav.settings')}>
                <summary>
                  <Icon name={group.icon} className="app-nav-section-icon" />
                  <span>{t(group.labelKey)}</span>
                  <Icon name="chevron" className="app-nav-caret" />
                </summary>
                <div className="app-nav-section-items">
                  {group.items.map(renderItem)}
                </div>
              </details>
            );
          })}
        </nav>
        <a className="app-manual-link" href="/manual-usuario.html" target="_blank" rel="noopener noreferrer"><Icon name="form" /><span>{t('nav.userManual')}</span></a>
        <LanguageSelector className="app-lang-selector" />
        <small>InfoMatt360</small>
      </aside>
      <section className="app-main">
        <header className="app-header">
          <h1>{title}</h1>
          <div className="app-header-actions">
            {projects.length > 1 ? (
              <label>
                {t('auth.project')}
                <select value={selectedProjectId} onChange={(event) => changeProject(event.target.value)}>
                  {projects.map((project) => <option key={project.id} value={project.id}>{project.name}{projectCounts[project.id] ? ` · ${projectCounts[project.id]} ${t('auth.assigned')}` : ''}</option>)}
                </select>
              </label>
            ) : projects[0] ? <span>{projects[0].name}</span> : null}
            <OfflineSyncStatus />
            <button className="app-logout" onClick={() => void closeSession()}>{t('auth.logout')}</button>
          </div>
        </header>
        {children}
      </section>
    </div>
  );
}
