import { useEffect, useMemo, useState } from 'react';
import { MapContainer, Marker, Polygon, Polyline, Popup, TileLayer, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png';
import markerIcon from 'leaflet/dist/images/marker-icon.png';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchNearbyFeatures, fetchProjectMap } from './api';
import type { MapFeature, ProjectMap } from './api';

// Fix del icono default de Leaflet, roto por bundlers que no resuelven las
// rutas relativas del paquete como en un build clasico.
delete (L.Icon.Default.prototype as { _getIconUrl?: unknown })._getIconUrl;
L.Icon.Default.mergeOptions({ iconRetinaUrl: markerIcon2x, iconUrl: markerIcon, shadowUrl: markerShadow });

const DEFAULT_CENTER: [number, number] = [4.711, -74.0721];

type GeoJsonGeometry =
  | { type: 'Point'; coordinates: [number, number] }
  | { type: 'LineString'; coordinates: [number, number][] }
  | { type: 'Polygon'; coordinates: [number, number][][] };

function parseGeometry(feature: MapFeature): GeoJsonGeometry | null {
  if (!feature.geometry_json) return null;
  try {
    const parsed = JSON.parse(feature.geometry_json);
    if (parsed && (parsed.type === 'Point' || parsed.type === 'LineString' || parsed.type === 'Polygon')) return parsed;
  } catch {
    return null;
  }
  return null;
}

function toLatLng([longitude, latitude]: [number, number]): [number, number] {
  return [latitude, longitude];
}

export function MapsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [map, setMap] = useState<ProjectMap | null>(null);
  const [displayedFeatures, setDisplayedFeatures] = useState<MapFeature[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [clickedCenter, setClickedCenter] = useState<[number, number] | null>(null);
  const [radiusKm, setRadiusKm] = useState(1);
  const [filtered, setFiltered] = useState(false);
  const [message, setMessage] = useState('Cargando mapa...');

  useEffect(() => {
    fetchProjectMap(projectId)
      .then((data) => {
        setMap(data);
        setDisplayedFeatures(data.features);
        setSelectedId(data.features[0]?.id ?? null);
        setMessage(data.features.length ? '' : 'Este proyecto aún no tiene coordenadas capturadas.');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const selected = displayedFeatures.find((feature) => feature.id === selectedId) ?? null;
  const center: [number, number] = useMemo(() => {
    const first = map?.features[0];
    return first ? [first.latitude, first.longitude] : DEFAULT_CENTER;
  }, [map]);

  async function searchNearby() {
    const origin = clickedCenter ?? (selected ? ([selected.latitude, selected.longitude] as [number, number]) : null);
    if (!origin) {
      setMessage('Toca un punto del mapa o selecciona un elemento para buscar cerca.');
      return;
    }
    try {
      const results = await fetchNearbyFeatures(projectId, origin[0], origin[1], radiusKm);
      setDisplayedFeatures(results);
      setFiltered(true);
      setMessage(results.length ? '' : 'No hay elementos dentro del radio indicado.');
    } catch (error) {
      setMessage((error as Error).message);
    }
  }

  function clearFilter() {
    setDisplayedFeatures(map?.features ?? []);
    setFiltered(false);
    setClickedCenter(null);
    setMessage(map?.features.length ? '' : 'Este proyecto aún no tiene coordenadas capturadas.');
  }

  return (
    <AppShell title="Mapas">
      <main className="maps-shell">
        {message ? <p role="status">{message}</p> : null}
        <section className="maps-layout">
          <div className="maps-canvas-card">
            <header>
              <div>
                <h2>Ubicaciones capturadas</h2>
                <p>{displayedFeatures.length.toLocaleString()} elemento(s) con coordenadas{filtered ? ' (filtrado por cercanía)' : ''}.</p>
              </div>
              <a href="/records">Ver registros</a>
            </header>
            <div className="maps-nearby-panel">
              <label>
                Radio (km)
                <input type="number" min={0.1} step={0.1} value={radiusKm} onChange={(event) => setRadiusKm(Number(event.target.value) || 1)} />
              </label>
              <button type="button" onClick={searchNearby}>Buscar cerca de este punto</button>
              {filtered ? <button type="button" onClick={clearFilter}>Limpiar filtro</button> : null}
              <span className="maps-nearby-hint">
                {clickedCenter ? 'Centro: punto elegido en el mapa.' : selected ? `Centro: ${selected.label}.` : 'Toca el mapa para elegir un centro.'}
              </span>
            </div>
            <MapContainer center={center} zoom={13} className="maps-leaflet-container">
              <TileLayer url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" attribution="&copy; OpenStreetMap contributors" />
              <MapClickHandler onClick={(lat, lng) => setClickedCenter([lat, lng])} />
              {displayedFeatures.map((feature) => {
                const geometry = parseGeometry(feature);
                if (geometry?.type === 'LineString') {
                  return <Polyline key={feature.id} positions={geometry.coordinates.map(toLatLng)} eventHandlers={{ click: () => setSelectedId(feature.id) }} />;
                }
                if (geometry?.type === 'Polygon') {
                  return <Polygon key={feature.id} positions={(geometry.coordinates[0] ?? []).map(toLatLng)} eventHandlers={{ click: () => setSelectedId(feature.id) }} />;
                }
                return (
                  <Marker key={feature.id} position={[feature.latitude, feature.longitude]} eventHandlers={{ click: () => setSelectedId(feature.id) }}>
                    <Popup>{feature.label}</Popup>
                  </Marker>
                );
              })}
            </MapContainer>
          </div>
          <aside className="maps-detail">
            <h2>Detalle</h2>
            {selected ? (
              <>
                <strong>{selected.label}</strong>
                <span className={`maps-source ${selected.source}`}>{selected.source === 'runtime' ? 'Registro Runtime' : 'Capa GIS'}</span>
                <dl>
                  <div><dt>Tipo</dt><dd>{selected.feature_type}</dd></div>
                  <div><dt>Latitud</dt><dd>{selected.latitude.toFixed(6)}</dd></div>
                  <div><dt>Longitud</dt><dd>{selected.longitude.toFixed(6)}</dd></div>
                  <div><dt>Formulario</dt><dd>{selected.template_name || 'No aplica'}</dd></div>
                  <div><dt>Registro</dt><dd>{selected.record_id || 'No asociado'}</dd></div>
                </dl>
                {selected.template_id ? <a href={`/records/${selected.template_id}`}>Abrir registros del formulario</a> : null}
              </>
            ) : <p>Selecciona un punto del mapa para ver su detalle.</p>}
          </aside>
        </section>
      </main>
    </AppShell>
  );
}

function MapClickHandler({ onClick }: { onClick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (event) => onClick(event.latlng.lat, event.latlng.lng) });
  return null;
}
