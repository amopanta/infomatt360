import React, { lazy, Suspense, useEffect, useState } from 'react';
import ReactDOM from 'react-dom/client';
import { AuthGate } from './modules/auth/AuthGate';
import { applyFallbackBranding, loadOrganizationBranding } from './modules/branding/brandingLoader';
import { hasAnyCurrentProjectPermission, PROJECT_KEY } from './modules/auth/session';
import { AppShell } from './components/AppShell';
import { DashboardApp } from './modules/dashboard/DashboardApp';
import { APP_NAVIGATION_EVENT, navigateTo, resolveAppRoute } from './routeConfig';
import type { AppRoute } from './routeConfig';
import { I18nProvider, useI18n } from './i18n';
import './styles.css';

// Cada pantalla se descarga solo cuando se abre (antes todo iba en un solo
// archivo de ~1.2 MB, lento con mala señal en campo).
const AccountSecurityApp = lazy(() => import('./modules/account/AccountSecurityApp').then((module) => ({ default: module.AccountSecurityApp })));
const ActaApp = lazy(() => import('./modules/acta/ActaApp').then((module) => ({ default: module.ActaApp })));
const AdminUserSecurityApp = lazy(() => import('./modules/admin/AdminUserSecurityApp').then((module) => ({ default: module.AdminUserSecurityApp })));
const AiAuditApp = lazy(() => import('./modules/admin/AiAuditApp').then((module) => ({ default: module.AiAuditApp })));
const ApiKeysApp = lazy(() => import('./modules/admin/ApiKeysApp').then((module) => ({ default: module.ApiKeysApp })));
const ApprovalFlowsApp = lazy(() => import('./modules/admin/ApprovalFlowsApp').then((module) => ({ default: module.ApprovalFlowsApp })));
const BackupsApp = lazy(() => import('./modules/admin/BackupsApp').then((module) => ({ default: module.BackupsApp })));
const BulkJobsApp = lazy(() => import('./modules/admin/BulkJobsApp').then((module) => ({ default: module.BulkJobsApp })));
const DonorSyncApp = lazy(() => import('./modules/admin/DonorSyncApp').then((module) => ({ default: module.DonorSyncApp })));
const ErpApp = lazy(() => import('./modules/admin/ErpApp').then((module) => ({ default: module.ErpApp })));
const ExcelImportApp = lazy(() => import('./modules/admin/ExcelImportApp').then((module) => ({ default: module.ExcelImportApp })));
const GovernanceApp = lazy(() => import('./modules/admin/GovernanceApp').then((module) => ({ default: module.GovernanceApp })));
const BrandingApp = lazy(() => import('./modules/admin/BrandingApp').then((module) => ({ default: module.BrandingApp })));
const MailProfilesApp = lazy(() => import('./modules/admin/MailProfilesApp').then((module) => ({ default: module.MailProfilesApp })));
const OperationalMetricsApp = lazy(() => import('./modules/admin/OperationalMetricsApp').then((module) => ({ default: module.OperationalMetricsApp })));
const PublicLinksApp = lazy(() => import('./modules/admin/PublicLinksApp').then((module) => ({ default: module.PublicLinksApp })));
const StorageApp = lazy(() => import('./modules/admin/StorageApp').then((module) => ({ default: module.StorageApp })));
const XlsformApp = lazy(() => import('./modules/admin/XlsformApp').then((module) => ({ default: module.XlsformApp })));
const MirrorApp = lazy(() => import('./modules/admin/MirrorApp').then((module) => ({ default: module.MirrorApp })));
const WhatsAppApp = lazy(() => import('./modules/admin/WhatsAppApp').then((module) => ({ default: module.WhatsAppApp })));
const AuditApp = lazy(() => import('./modules/audit/AuditApp').then((module) => ({ default: module.AuditApp })));
const BuilderApp = lazy(() => import('./modules/builder/BuilderApp').then((module) => ({ default: module.BuilderApp })));
const FormsApp = lazy(() => import('./modules/builder/FormsApp').then((module) => ({ default: module.FormsApp })));
const MyFormsApp = lazy(() => import('./modules/builder/MyFormsApp').then((module) => ({ default: module.MyFormsApp })));
const MapsApp = lazy(() => import('./modules/maps/MapsApp').then((module) => ({ default: module.MapsApp })));
const MessagesApp = lazy(() => import('./modules/messages/MessagesApp').then((module) => ({ default: module.MessagesApp })));
const ParticipantsApp = lazy(() => import('./modules/participants/ParticipantsApp').then((module) => ({ default: module.ParticipantsApp })));
const AppliedActivitiesApp = lazy(() => import('./modules/participants/AppliedActivitiesApp').then((module) => ({ default: module.AppliedActivitiesApp })));
const FieldDevicesApp = lazy(() => import('./modules/devices/FieldDevicesApp').then((module) => ({ default: module.FieldDevicesApp })));
const TeamsApp = lazy(() => import('./modules/teams/TeamsApp').then((module) => ({ default: module.TeamsApp })));
const RecordsApp = lazy(() => import('./modules/records/RecordsApp').then((module) => ({ default: module.RecordsApp })));
const ReportsApp = lazy(() => import('./modules/reports/ReportsApp').then((module) => ({ default: module.ReportsApp })));
const ReportCatalogApp = lazy(() => import('./modules/reports/ReportCatalogApp').then((module) => ({ default: module.ReportCatalogApp })));
const FormReportApp = lazy(() => import('./modules/reports/FormReportApp').then((module) => ({ default: module.FormReportApp })));
const IndicatorLibraryApp = lazy(() => import('./modules/reports/IndicatorLibraryApp').then((module) => ({ default: module.IndicatorLibraryApp })));
const EvidenceApp = lazy(() => import('./modules/evidence/EvidenceApp').then((module) => ({ default: module.EvidenceApp })));
const RuntimeApp = lazy(() => import('./modules/runtime/RuntimeApp').then((module) => ({ default: module.RuntimeApp })));

function PermissionGate({ permissions, children }: { permissions: string[]; children: React.ReactNode }) {
  const { t } = useI18n();
  if (hasAnyCurrentProjectPermission(permissions)) return <>{children}</>;
  return (
    <AppShell title={t('errors.forbidden')}>
      <main className="access-denied">
        <h2>{t('errors.forbidden')}</h2>
        <p>{t('auth.noProjects')}</p>
        <a href="/">{t('app.back')}</a>
      </main>
    </AppShell>
  );
}

function AppRouter() {
  const [navigation, setNavigation] = useState({ pathname: window.location.pathname, revision: 0 });

  useEffect(() => {
    function syncPath() {
      setNavigation((current) => ({ pathname: window.location.pathname, revision: current.revision + 1 }));
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

  return <React.Fragment key={localStorage.getItem(PROJECT_KEY) || navigation.pathname}>{renderRoute(resolveAppRoute(navigation.pathname))}</React.Fragment>;
}

function renderRoute(route: AppRoute) {
  const content = (() => {
    switch (route.key) {
      case 'builder': return window.location.pathname === '/builder/new' || window.location.pathname.startsWith('/builder/edit/') ? <BuilderApp /> : <FormsApp />;
      case 'myForms': return <MyFormsApp />;
      case 'acta': return <ActaApp />;
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
      case 'mirror': return <MirrorApp />;
      case 'excelImport': return <ExcelImportApp />;
      case 'storage': return <StorageApp />;
      case 'mailProfiles': return <MailProfilesApp />;
      case 'brandingAdmin': return <BrandingApp />;
      case 'publicLinks': return <PublicLinksApp />;
      case 'xlsform': return <XlsformApp />;
      case 'adminUsers': return <AdminUserSecurityApp />;
      case 'accountSecurity': return <AccountSecurityApp />;
      case 'participants': return <ParticipantsApp />;
      case 'appliedActivities': return <AppliedActivitiesApp />;
      case 'teams': return <TeamsApp />;
      case 'fieldDevices': return <FieldDevicesApp />;
      case 'records': return <RecordsApp />;
      case 'reports': return window.location.pathname.startsWith('/reports/form/') ? <FormReportApp /> : window.location.pathname.startsWith('/reports/indicators') ? <IndicatorLibraryApp /> : window.location.pathname.startsWith('/reports/catalog') ? <ReportCatalogApp /> : <ReportsApp />;
      case 'evidence': return <EvidenceApp />;
      case 'maps': return <MapsApp />;
      case 'messages': return <MessagesApp />;
      case 'audit': return <AuditApp />;
      case 'runtime': return <RuntimeApp />;
      case 'dashboard': return <DashboardApp />;
    }
  })();
  const page = <Suspense fallback={<p className="route-loading" role="status">…</p>}>{content}</Suspense>;
  return route.permissions ? <PermissionGate permissions={route.permissions}>{page}</PermissionGate> : page;
}

applyFallbackBranding();
void loadOrganizationBranding();

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <I18nProvider>
      <AuthGate><AppRouter /></AuthGate>
    </I18nProvider>
  </React.StrictMode>,
);
