import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { hasAnyCurrentProjectPermission, PROJECT_KEY } from '../auth/session';
import { fetchDeviceStatus, requestRemoteWipe, serverDate, type FieldDeviceStatus } from './api';
import { RouteVisits } from './RouteVisits';

const REFRESH_MS = 60_000;

/** "hace 5 min", "hace 3 h", "hace 2 días" */
function useAgo() {
  const { t } = useI18n();
  return (value: string | null) => {
    const date = serverDate(value);
    if (!date) return t('ux.devices.never');
    const minutes = Math.max(0, Math.round((Date.now() - date.getTime()) / 60_000));
    if (minutes < 1) return t('ux.devices.justNow');
    if (minutes < 60) return t('ux.devices.minutesAgo', { count: minutes });
    const hours = Math.round(minutes / 60);
    if (hours < 48) return t('ux.devices.hoursAgo', { count: hours });
    return t('ux.devices.daysAgo', { count: Math.round(hours / 24) });
  };
}

export function FieldDevicesApp() {
  const { t } = useI18n();
  const ago = useAgo();
  const projectId = localStorage.getItem(PROJECT_KEY) || '';
  const [devices, setDevices] = useState<FieldDeviceStatus[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [filter, setFilter] = useState<'all' | 'attention'>('all');
  const [expanded, setExpanded] = useState('');
  const [routeUser, setRouteUser] = useState('');
  // «Recorridos y visitas» tiene su propia entrada en el menú y abre solo esa
  // parte; «Equipos de campo» la muestra debajo de las tablets (docs/150).
  const routesOnly = window.location.pathname.startsWith('/field-devices/routes');
  const [message, setMessage] = useState('');
  const canWipe = hasAnyCurrentProjectPermission(['identity.users.manage']);

  async function wipe(device: FieldDeviceStatus) {
    if (!window.confirm(t('ux.devices.wipeConfirm', { user: device.user_name, device: device.device_name || device.device_id.slice(0, 8) }))) return;
    try {
      const updated = await requestRemoteWipe(projectId, device.device_id, device.user_id);
      setDevices((rows) => rows.map((row) => (row.device_id === updated.device_id && row.user_id === updated.user_id ? updated : row)));
      setMessage(t('ux.devices.wipeRequested'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : String(error));
    }
  }

  useEffect(() => {
    if (!projectId) return;
    const load = () => fetchDeviceStatus(projectId).then((rows) => { setDevices(rows); setLoaded(true); }).catch((error: Error) => setMessage(error.message));
    void load();
    const timer = window.setInterval(load, REFRESH_MS);
    return () => window.clearInterval(timer);
  }, [projectId]);

  const totals = useMemo(() => ({
    devices: devices.length,
    attention: devices.filter((d) => d.level !== 'ok').length,
    pending: devices.reduce((sum, d) => sum + d.pending_count, 0),
    errors: devices.reduce((sum, d) => sum + d.error_count + d.conflict_count, 0),
  }), [devices]);
  const visible = filter === 'attention' ? devices.filter((d) => d.level !== 'ok') : devices;

  function showRoute(userId: string) {
    setRouteUser(userId);
    window.setTimeout(() => document.getElementById('field-route')?.scrollIntoView({ behavior: 'smooth' }), 50);
  }

  if (routesOnly) return <AppShell title={t('ux.devices.routesNav')}><main className="devices-page"><RouteVisits projectId={projectId} /></main></AppShell>;

  return <AppShell title={t('ux.devices.title')}><main className="devices-page">
    <h1>{t('ux.devices.title')}</h1>
    <p>{t('ux.devices.description')}</p>

    <section className="devices-totals" aria-label={t('ux.devices.summary')}>
      <div><strong>{totals.devices}</strong><span>{t('ux.devices.totalDevices')}</span></div>
      <div className={totals.attention ? 'is-warning' : ''}><strong>{totals.attention}</strong><span>{t('ux.devices.needAttention')}</span></div>
      <div className={totals.pending ? 'is-warning' : ''}><strong>{totals.pending}</strong><span>{t('ux.devices.unsentRecords')}</span></div>
      <div className={totals.errors ? 'is-danger' : ''}><strong>{totals.errors}</strong><span>{t('ux.devices.recordsWithErrors')}</span></div>
    </section>

    <section className="teams-card">
      <div className="devices-head">
        <h2>{t('ux.devices.listTitle')}</h2>
        <div className="my-forms-views" role="group">
          <button type="button" aria-current={filter === 'all' ? 'page' : undefined} onClick={() => setFilter('all')}>{t('ux.devices.filterAll')}</button>
          <button type="button" aria-current={filter === 'attention' ? 'page' : undefined} onClick={() => setFilter('attention')}>{t('ux.devices.filterAttention')}</button>
        </div>
      </div>
      {loaded && !devices.length && <p>{t('ux.devices.empty')}</p>}
      <div className="devices-list">
        {visible.map((device) => {
          const key = `${device.device_id}:${device.user_id}`;
          return <article key={key} className={`device-card level-${device.level}`}>
            <header>
              <span className="device-dot" aria-hidden="true" />
              <div>
                <strong>{device.user_name}</strong>
                <small>{device.device_name || device.device_id.slice(0, 8)} · {device.platform} {device.app_version && `· v${device.app_version}`}</small>
              </div>
              <span className="device-level">{t(`ux.devices.level.${device.level}`)}</span>
            </header>
            <dl>
              <div><dt>{t('ux.devices.unsent')}</dt><dd>{device.pending_count}{device.pending_evidence_count ? ` + ${t('ux.devices.files', { count: device.pending_evidence_count })}` : ''}</dd></div>
              <div><dt>{t('ux.devices.errors')}</dt><dd>{device.error_count + device.conflict_count}</dd></div>
              <div><dt>{t('ux.devices.lastSync')}</dt><dd>{ago(device.last_sync_at)}</dd></div>
              <div><dt>{t('ux.devices.lastSeen')}</dt><dd>{ago(device.last_seen_at)}</dd></div>
            </dl>
            {device.alerts.length > 0 && <ul className="device-alerts">{device.alerts.map((alert) => <li key={alert}>{alert}</li>)}</ul>}
            {device.wipe_requested_at && <p className="devices-note">{device.wipe_completed_at
              ? t('ux.devices.wipeDone', { when: serverDate(device.wipe_completed_at)?.toLocaleString() ?? '' })
              : t('ux.devices.wipePending', { when: ago(device.wipe_requested_at) })}</p>}
            <div className="teams-inline">
              {device.recent_errors.length > 0 && <button type="button" onClick={() => setExpanded(expanded === key ? '' : key)}>{expanded === key ? t('ux.devices.hideErrors') : t('ux.devices.showErrors', { count: device.recent_errors.length })}</button>}
              <button type="button" onClick={() => showRoute(device.user_id)}>{t('ux.devices.viewRoute')}</button>
              {canWipe && !(device.wipe_requested_at && !device.wipe_completed_at) && <button type="button" className="danger" onClick={() => void wipe(device)}>{t('ux.devices.wipe')}</button>}
            </div>
            {expanded === key && <ol className="device-errors">{device.recent_errors.map((error, index) => <li key={index}><time>{error.at ? serverDate(error.at)?.toLocaleString() : ''}</time> {error.message}</li>)}</ol>}
          </article>;
        })}
      </div>
    </section>

    <RouteVisits projectId={projectId} initialUser={routeUser} />
    {message && <p role="status">{message}</p>}
  </main></AppShell>;
}
