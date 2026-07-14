import { describe, expect, it } from 'vitest';
import { resolveAppRoute } from './routeConfig';

describe('resolveAppRoute', () => {
  it('mapea rutas funcionales principales', () => {
    expect(resolveAppRoute('/').key).toBe('dashboard');
    expect(resolveAppRoute('/participants').key).toBe('participants');
    expect(resolveAppRoute('/participants/participant-1').key).toBe('participants');
    expect(resolveAppRoute('/records').key).toBe('records');
    expect(resolveAppRoute('/records/template-1').key).toBe('records');
    expect(resolveAppRoute('/reports').key).toBe('reports');
    expect(resolveAppRoute('/maps').key).toBe('maps');
    expect(resolveAppRoute('/messages').key).toBe('messages');
    expect(resolveAppRoute('/audit').key).toBe('audit');
    expect(resolveAppRoute('/runtime/template-1').key).toBe('runtime');
    expect(resolveAppRoute('/account/security').key).toBe('accountSecurity');
  });

  it('mapea rutas administrativas con permisos esperados', () => {
    expect(resolveAppRoute('/builder')).toEqual({ key: 'builder', permissions: ['builder.write'] });
    expect(resolveAppRoute('/admin/users')).toEqual({ key: 'adminUsers', permissions: ['identity.users.manage'] });
    expect(resolveAppRoute('/admin/api-keys')).toEqual({ key: 'apiKeys', permissions: ['integrations.api_keys.manage'] });
    expect(resolveAppRoute('/admin/approval-flows')).toEqual({ key: 'approvalFlows', permissions: ['records.approve'] });
    expect(resolveAppRoute('/admin/bulk-jobs')).toEqual({ key: 'bulkJobs', permissions: ['integrations.api_keys.manage', 'records.write'] });
    expect(resolveAppRoute('/admin/metrics')).toEqual({ key: 'metrics', permissions: ['identity.users.manage', 'integrations.api_keys.manage', 'records.approve', 'records.write'] });
  });

  it('prioriza rutas administrativas especificas antes que rutas generales', () => {
    expect(resolveAppRoute('/admin/api-keys/abc')).toEqual({ key: 'apiKeys', permissions: ['integrations.api_keys.manage'] });
    expect(resolveAppRoute('/admin/bulk-jobs/job-1')).toEqual({ key: 'bulkJobs', permissions: ['integrations.api_keys.manage', 'records.write'] });
  });
});
