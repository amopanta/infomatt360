import { useEffect, useMemo, useState } from 'react';
import { CircleMarker, MapContainer, Polyline, Popup, TileLayer, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';

import { useI18n } from '../../i18n';
import { operationalStatusLabel } from '../../lib/operationalFormat';
import { fetchRouteDays, fetchRoutes, fetchVisits, serverDate, type RouteDay, type RouteSummary, type Visit } from './api';

function today(): string {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

function time(value: string | null) {
  const date = serverDate(value);
  return date ? date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';
}

function dayLabel(day: string, locale: string) {
  return new Date(`${day}T12:00:00`).toLocaleDateString(locale === 'en' ? 'en' : 'es-CO', { weekday: 'short', day: 'numeric', month: 'short' });
}

/** Recorrido del gestor y visitas del día: por dónde pasó, a quién visitó y
 * dónde quedó cada formulario. Abre en el último día con datos, no en un
 * «hoy» vacío (docs/150). */
export function RouteVisits({ projectId, initialUser = '' }: { projectId: string; initialUser?: string }) {
  const { t, locale } = useI18n();
  const [days, setDays] = useState<RouteDay[]>([]);
  const [day, setDay] = useState('');
  const [routes, setRoutes] = useState<RouteSummary[]>([]);
  const [routeUser, setRouteUser] = useState(initialUser);
  const [route, setRoute] = useState<RouteSummary | null>(null);
  const [visits, setVisits] = useState<Visit[]>([]);
  const [message, setMessage] = useState('');

  useEffect(() => { setRouteUser(initialUser); }, [initialUser]);

  useEffect(() => {
    if (!projectId) return;
    void fetchRouteDays(projectId)
      .then((rows) => { setDays(rows); setDay((current) => current || rows[0]?.day || today()); })
      .catch(() => setDay((current) => current || today()));
  }, [projectId]);

  useEffect(() => {
    if (!projectId || !day) return;
    void fetchRoutes(projectId, day).then((rows) => {
      setRoutes(rows);
      setRouteUser((current) => current && rows.some((row) => row.user_id === current) ? current : rows[0]?.user_id ?? '');
    }).catch((error: Error) => setMessage(error.message));
  }, [projectId, day]);

  useEffect(() => {
    if (!projectId || !day) return;
    if (!routeUser) { setRoute(null); return; }
    void fetchRoutes(projectId, day, routeUser).then((rows) => setRoute(rows[0] ?? null)).catch((error: Error) => setMessage(error.message));
  }, [projectId, day, routeUser]);

  useEffect(() => {
    if (!projectId || !day) return;
    void fetchVisits(projectId, day, routeUser || undefined).then(setVisits).catch(() => setVisits([]));
  }, [projectId, day, routeUser]);

  const path = useMemo(() => (route?.points ?? []).map((p) => [p.latitude, p.longitude] as [number, number]), [route]);
  const located = visits.filter((visit) => visit.latitude !== null && visit.longitude !== null);
  const bounds = useMemo(() => [...path, ...located.map((v) => [v.latitude as number, v.longitude as number] as [number, number])], [path, located]);
  const recentDays = days.slice(0, 7);

  return (
    <section className="route-visits" id="field-route" aria-labelledby="route-visits-title">
      <header className="route-visits-head">
        <div>
          <h2 id="route-visits-title">{t('ux.devices.routeTitle')}</h2>
          <p>{t('ux.devices.routePrivacy')}</p>
        </div>
        <label>{t('ux.devices.day')}<input type="date" value={day} max={today()} onChange={(event) => setDay(event.target.value || today())} /></label>
      </header>

      {recentDays.length > 0 && (
        <div className="route-days" role="group" aria-label={t('ux.devices.daysWithRoutes')}>
          <span>{t('ux.devices.daysWithRoutes')}</span>
          {recentDays.map((item) => (
            <button key={item.day} type="button" aria-pressed={item.day === day} onClick={() => setDay(item.day)}>
              {dayLabel(item.day, locale)}<small>{t('ux.devices.dayCounts', { users: item.user_count, visits: item.visit_count })}</small>
            </button>
          ))}
        </div>
      )}

      {!routes.length && !visits.length ? <p className="empty-note">{days.length ? t('ux.devices.noRoutes') : t('ux.devices.noRoutesYet')}</p> : (
        <div className="route-visits-body">
          <aside className="route-people">
            {routes.map((item) => (
              <button type="button" key={item.user_id} aria-pressed={routeUser === item.user_id} onClick={() => setRouteUser(item.user_id)}>
                <strong>{item.user_name}</strong>
                <span>{t('ux.devices.routeSummary', { km: item.distance_km.toLocaleString(undefined, { maximumFractionDigits: 1 }), points: item.point_count, from: time(item.first_at), to: time(item.last_at) })}</span>
              </button>
            ))}
          </aside>
          <div className="route-map-column">
            {bounds.length > 0 ? (
              <MapContainer key={`${routeUser}-${day}-${bounds.length}`} className="devices-map" bounds={bounds} boundsOptions={{ padding: [30, 30], maxZoom: 17 }} scrollWheelZoom={false}>
                <TileLayer attribution='&copy; OpenStreetMap' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {path.length > 1 && <Polyline positions={path} pathOptions={{ color: '#0066cc', weight: 4, opacity: 0.75 }} />}
                {route?.points.map((point, index) => {
                  const edge = index === 0 || index === route.points.length - 1;
                  if (!edge) return null;
                  return <CircleMarker key={point.recorded_at} center={[point.latitude, point.longitude]} radius={7}
                    pathOptions={{ color: index === 0 ? '#15803d' : '#475569', fillOpacity: 0.9 }}>
                    <Popup>{index === 0 ? t('ux.devices.start') : t('ux.devices.end')} {time(point.recorded_at)}</Popup>
                  </CircleMarker>;
                })}
                {located.map((visit) => (
                  <CircleMarker key={visit.record_id} center={[visit.latitude as number, visit.longitude as number]} radius={9}
                    pathOptions={{ color: '#ffffff', weight: 2, fillColor: '#c2410c', fillOpacity: 1 }}>
                    <Tooltip direction="top" offset={[0, -8]}>{visits.indexOf(visit) + 1}. {visit.participant_name ?? visit.template_name}</Tooltip>
                    <Popup><strong>{visit.participant_name ?? t('ux.devices.noParticipant')}</strong><br />{visit.template_name} · {time(visit.created_at)}</Popup>
                  </CircleMarker>
                ))}
              </MapContainer>
            ) : <p className="empty-note">{t('ux.devices.noRouteForUser')}</p>}
            <p className="route-legend"><span className="legend-line" />{t('ux.devices.legendRoute')}<span className="legend-dot visit" />{t('ux.devices.legendVisit')}<span className="legend-dot start" />{t('ux.devices.start')}</p>
          </div>
          <div className="route-visit-list">
            <h3>{t('ux.devices.visitsTitle', { count: visits.length })}</h3>
            {visits.length ? (
              <ol>
                {visits.map((visit, index) => (
                  <li key={visit.record_id}>
                    <span className="visit-index" aria-hidden="true">{index + 1}</span>
                    <div>
                      <strong>{visit.participant_name ?? t('ux.devices.noParticipant')}</strong>
                      <small>{time(visit.created_at)} · {visit.template_name}{visit.participant_document ? ` · ${visit.participant_document}` : ''}</small>
                      <small>{visit.latitude === null ? t('ux.devices.noGps') : `${visit.latitude.toFixed(5)}, ${visit.longitude?.toFixed(5)}`} · {operationalStatusLabel(visit.status)}</small>
                    </div>
                    <a href={`/records/${visit.template_id}`}>{t('ux.devices.openRecord')}</a>
                  </li>
                ))}
              </ol>
            ) : <p className="empty-note">{t('ux.devices.noVisits')}</p>}
          </div>
        </div>
      )}
      {message && <p role="status">{message}</p>}
    </section>
  );
}
