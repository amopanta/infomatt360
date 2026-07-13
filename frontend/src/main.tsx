import React, { useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { AccountSecurityApp } from './modules/account/AccountSecurityApp';
import { AdminUserSecurityApp } from './modules/admin/AdminUserSecurityApp';
import { AiAuditApp } from './modules/admin/AiAuditApp';
import { ApiKeysApp } from './modules/admin/ApiKeysApp';
import { ApprovalFlowsApp } from './modules/admin/ApprovalFlowsApp';
import { BackupsApp } from './modules/admin/BackupsApp';
import { BulkJobsApp } from './modules/admin/BulkJobsApp';
import { DonorSyncApp } from './modules/admin/DonorSyncApp';
import { ErpApp } from './modules/admin/ErpApp';
import { ExcelImportApp } from './modules/admin/ExcelImportApp';
import { GovernanceApp } from './modules/admin/GovernanceApp';
import { MailProfilesApp } from './modules/admin/MailProfilesApp';
import { OperationalMetricsApp } from './modules/admin/OperationalMetricsApp';
import { StorageApp } from './modules/admin/StorageApp';
import { WhatsAppApp } from './modules/admin/WhatsAppApp';
import { AuditApp } from './modules/audit/AuditApp';
import { AuthGate } from './modules/auth/AuthGate';
import { applyFallbackBranding, loadOrganizationBranding } from './modules/branding/brandingLoader';
import { hasAnyCurrentProjectPermission } from './modules/auth/session';
import { BuilderApp } from './modules/builder/BuilderApp';
import { AppShell } from './components/AppShell';
import { DashboardApp } from './modules/dashboard/DashboardApp';
import { MapsApp } from './modules/maps/MapsApp';
import { MessagesApp } from './modules/messages/MessagesApp';
import { RecordsApp } from './modules/records/RecordsApp';
import { ReportsApp } from './modules/reports/ReportsApp';
import { RuntimeApp } from './modules/runtime/RuntimeApp';
import { APP_NAVIGATION_EVENT, navigateTo, resolveAppRoute } from './routeConfig';
import type { AppRoute } from './routeConfig';
import './styles.css';

function PermissionGate({ permissions, children }: { permissions: string[]; children: React.ReactNode }) {
  if (hasAnyCurrentProjectPermission(permissions)) return <>{children}</>;
  return (
    <AppShell title="Acceso restringido">
      <main className="access-denied">
        <h2>No tienes permiso para abrir este modulo</h2>
        <p>Si necesitas acceso, solicita al administrador del proyecto que ajuste tu rol o tus permisos.</p>
        <a href="/">Volver al dashboard</a>
      </main>
    </AppShell>
  );
}

function AppRouter() {
  const [pathname, setPathname] = useState(window.location.pathname);

  useEffect(() => {
    function syncPath() {
      setPathname(window.location.pathname);
    }

    function interceptInternalLinks(event: MouseEvent) {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const target = event.target instanceof Element ? event.target.closest('a') : null;
      if (!(target instanceof HTMLAnchorElement)) return;
      if (target.target || target.hasAttribute('download')) return;
      const url = new URL(target.href, window.location.href);
      if (url.origin !== window.location.origin) return;
      if (url.pathname === '/reset-password') return;
      event.preventDefault();
      navigateTo(`${url.pathname}${url.search}${url.hash}`);
    }

    window.addEventListener('popstate', syncPath);
    window.addEventListener(APP_NAVIGATION_EVENT, syncPath);
    document.addEventListener('click', interceptInternalLinks);
    return () => {
      window.removeEventListener('popstate', syncPath);
      window.removeEventListener(APP_NAVIGATION_EVENT, syncPath);
      document.removeEventListener('click', interceptInternalLinks);
    };
  }, []);

  return renderRoute(resolveAppRoute(pathname));
}

function renderRoute(route: AppRoute) {
  const content = (() => {
    switch (route.key) {
      case 'builder': return <BuilderApp />;
      case 'bulkJobs': return <BulkJobsApp />;
      case 'metrics': return <OperationalMetricsApp />;
      case 'approvalFlows': return <ApprovalFlowsApp />;
      case 'apiKeys': return <ApiKeysApp />;
      case 'erp': return <ErpApp />;
      case 'whatsapp': return <WhatsAppApp />;
      case 'donorSync': return <DonorSyncApp />;
      case 'aiAudit': return <AiAuditApp />;
      case 'governance': return <GovernanceApp />;
      case 'backups': return <BackupsApp />;
      case 'excelImport': return <ExcelImportApp />;
      case 'storage': return <StorageApp />;
      case 'mailProfiles': return <MailProfilesApp />;
      case 'adminUsers': return <AdminUserSecurityApp />;
      case 'accountSecurity': return <AccountSecurityApp />;
      case 'records': return <RecordsApp />;
      case 'reports': return <ReportsApp />;
      case 'maps': return <MapsApp />;
      case 'messages': return <MessagesApp />;
      case 'audit': return <AuditApp />;
      case 'runtime': return <RuntimeApp />;
      case 'dashboard': return <DashboardApp />;
    }
  })();
  return route.permissions ? <PermissionGate permissions={route.permissions}>{content}</PermissionGate> : content;
}

applyFallbackBranding();
void loadOrganizationBranding();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <AuthGate><AppRouter /></AuthGate>
  </React.StrictMode>,
);
