import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { hasAnyCurrentProjectPermission, PROJECT_KEY } from '../auth/session';
import { fetchDeviceStatus, fetchRoutes, requestRemoteWipe, serverDate, type FieldDeviceStatus, type RouteSummary } from './api';

const REFRESH_MS = 60_000;

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

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

function time(value: string | null) {
  const date = serverDate(value);
  return date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
}

export function FieldDevicesApp() {
  const { t } = useI18n();
  const ago = useAgo();
  const projectId = localStorage.getItem(PROJECT_KEY) || '';
  const [devices, setDevices] = useState<FieldDeviceStatus[]>([]);
  const [loaded, setLoaded] = useState(false);
  const [filter, setFilter] = useState<'all' | 'attention'>('all');
  const [expanded, setExpanded] = useState('');
  const [day, setDay] = useState(today());
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [routeUser, setRouteUser] = useState('');
  const [route, setRoute] = useState<RouteSummary | null>(null);
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

  useEffect(() => {
    if (!projectId) return;
    void fetchRoutes(projectId, day).then(setRoutes).catch((error: Error) => setMessage(error.message));
  }, [projectId, day]);

  useEffect(() => {
    if (!projectId || !routeUser) { setRoute(null); return; }
    void fetchRoutes(projectId, day, routeUser).then((rows) => setRoute(rows[0] ?? null)).catch((error: Error) => setMessage(error.message));
  }, [projectId, day, routeUser]);

  const totals = useMemo(() => ({
    devices: devices.length,
    attention: devices.filter((d) => d.level !== 'ok').length,
    pending: devices.reduce((sum, d) => sum + d.pending_count, 0),
    errors: devices.reduce((sum, d) => sum + d.error_count + d.conflict_count, 0),
  }), [devices]);
  const visible = filter === 'attention' ? devices.filter((d) => d.level !== 'ok') : devices;
  const path = useMemo(() => (route?.points ?? []).map((p) => [p.latitude, p.longitude] as [number, number]), [route]);

  function showRoute(userId: string) {
    setRouteUser(userId);
    window.setTimeout(() => document.getElementById('field-route')?.scrollIntoView({ behavior: 'smooth' }), 50);
  }

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

    <section className="teams-card" id="field-route">
      <div className="devices-head">
        <h2>{t('ux.devices.routeTitle')}</h2>
        <label>{t('ux.devices.day')} <input type="date" value={day} max={today()} onChange={(event) => setDay(event.target.value || today())} /></label>
      </div>
      <p className="devices-note">{t('ux.devices.routePrivacy')}</p>
      {!routes.length ? <p>{t('ux.devices.noRoutes')}</p> : <div className="devices-routes">
        <div className="teams-options">{routes.map((item) => (
          <button type="button" key={item.user_id} className={`teams-item ${routeUser === item.user_id ? 'selected' : ''}`} onClick={() => setRouteUser(item.user_id)}>
            {item.user_name}
            <small>{t('ux.devices.routeSummary', { km: item.distance_km.toLocaleString(undefined, { maximumFractionDigits: 1 }), points: item.point_count, from: time(item.first_at), to: time(item.last_at) })}</small>
          </button>
        ))}</div>
        {route && path.length > 0 && <MapContainer key={`${route.user_id}-${day}`} className="devices-map" bounds={path} boundsOptions={{ padding: [30, 30] }} scrollWheelZoom={false}>
          <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          <Polyline positions={path} pathOptions={{ color: '#0f766e', weight: 4 }} />
          {route.points.map((point, index) => {
            const edge = index === 0 || index === route.points.length - 1;
            return <CircleMarker key={point.recorded_at} center={[point.latitude, point.longitude]} radius={edge ? 8 : 4}
              pathOptions={{ color: index === 0 ? '#15803d' : edge ? '#b91c1c' : '#0f766e', fillOpacity: 0.9 }}>
              <Popup>{index === 0 ? t('ux.devices.start') : edge ? t('ux.devices.end') : ''} {serverDate(point.recorded_at)?.toLocaleTimeString()}{point.accuracy_m ? ` · ±${Math.round(point.accuracy_m)} m` : ''}</Popup>
            </CircleMarker>;
          })}
        </MapContainer>}
        {routeUser && !route && <p>{t('ux.devices.noRouteForUser')}</p>}
      </div>}
    </section>
    {message && <p role="status">{message}</p>}
  </main></AppShell>;
}
