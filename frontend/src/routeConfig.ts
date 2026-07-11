export type AppRouteKey =
  | 'builder'
  | 'bulkJobs'
  | 'metrics'
  | 'approvalFlows'
  | 'apiKeys'
  | 'erp'
  | 'whatsapp'
  | 'donorSync'
  | 'adminUsers'
  | 'accountSecurity'
  | 'records'
  | 'reports'
  | 'maps'
  | 'messages'
  | 'audit'
  | 'runtime'
  | 'dashboard';

export type AppRoute = {
  key: AppRouteKey;
  permissions?: string[];
};

export const APP_NAVIGATION_EVENT = 'infomatt360:navigate';

export function navigateTo(pathname: string): void {
  if (window.location.pathname === pathname) return;
  window.history.pushState({}, '', pathname);
  window.dispatchEvent(new Event(APP_NAVIGATION_EVENT));
}

export function resolveAppRoute(pathname: string): AppRoute {
  if (pathname.startsWith('/builder')) return { key: 'builder', permissions: ['builder.write'] };
  if (pathname.startsWith('/admin/bulk-jobs')) return { key: 'bulkJobs', permissions: ['integrations.api_keys.manage', 'records.write'] };
  if (pathname.startsWith('/admin/metrics')) return { key: 'metrics', permissions: ['identity.users.manage', 'integrations.api_keys.manage', 'records.approve', 'records.write'] };
  if (pathname.startsWith('/admin/approval-flows')) return { key: 'approvalFlows', permissions: ['records.approve'] };
  if (pathname.startsWith('/admin/api-keys')) return { key: 'apiKeys', permissions: ['integrations.api_keys.manage'] };
  if (pathname.startsWith('/admin/erp')) return { key: 'erp', permissions: ['erp.manage'] };
  if (pathname.startsWith('/admin/whatsapp')) return { key: 'whatsapp', permissions: ['messages.read', 'records.review', 'records.approve'] };
  if (pathname.startsWith('/admin/donor-sync')) return { key: 'donorSync', permissions: ['integrations.donor_sync.manage'] };
  if (pathname.startsWith('/admin/users')) return { key: 'adminUsers', permissions: ['identity.users.manage'] };
  if (pathname.startsWith('/account/security')) return { key: 'accountSecurity' };
  if (pathname.startsWith('/records')) return { key: 'records' };
  if (pathname.startsWith('/reports')) return { key: 'reports' };
  if (pathname.startsWith('/maps')) return { key: 'maps' };
  if (pathname.startsWith('/messages')) return { key: 'messages' };
  if (pathname.startsWith('/audit')) return { key: 'audit' };
  if (pathname.startsWith('/runtime')) return { key: 'runtime' };
  return { key: 'dashboard' };
}
