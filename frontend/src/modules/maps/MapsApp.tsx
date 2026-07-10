import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { geometryViewport, projectCoordinate } from '../runtime/geoEngine';
import { fetchProjectMap } from './api';
import type { MapFeature, ProjectMap } from './api';

const MAP_WIDTH = 920;
const MAP_HEIGHT = 520;

export function MapsApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [map, setMap] = useState<ProjectMap | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [message, setMessage] = useState('Cargando mapa...');

  useEffect(() => {
    fetchProjectMap(projectId)
      .then((data) => {
        setMap(data);
        setSelectedId(data.features[0]?.id ?? null);
        setMessage(data.features.length ? '' : 'Este proyecto aún no tiene coordenadas capturadas.');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  const selected = map?.features.find((feature) => feature.id === selectedId) ?? null;

  return (
    <AppShell title="Mapas">
      <main className="maps-shell">
        {message ? <p role="status">{message}</p> : null}
        {map ? <MapContent features={map.features} selected={selected} onSelect={setSelectedId} /> : null}
      </main>
    </AppShell>
  );
}

function MapContent({ features, selected, onSelect }: { features: MapFeature[]; selected: MapFeature | null; onSelect: (id: string) => void }) {
  const viewport = useMemo(() => geometryViewport(features.map((feature) => [feature.longitude, feature.latitude])), [features]);
  return (
    <section className="maps-layout">
      <div className="maps-canvas-card">
        <header>
          <div>
            <h2>Ubicaciones capturadas</h2>
            <p>{features.length.toLocaleString()} elemento(s) con coordenadas.</p>
          </div>
          <a href="/records">Ver registros</a>
        </header>
        <svg className="maps-canvas" viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`} role="img" aria-label="Mapa operativo del proyecto">
          <rect className="maps-background" width={MAP_WIDTH} height={MAP_HEIGHT} rx="18" />
          {Array.from({ length: 7 }).map((_, index) => <line key={`v-${index}`} className="maps-grid" x1={(MAP_WIDTH / 6) * index} y1="0" x2={(MAP_WIDTH / 6) * index} y2={MAP_HEIGHT} />)}
          {Array.from({ length: 5 }).map((_, index) => <line key={`h-${index}`} className="maps-grid" x1="0" y1={(MAP_HEIGHT / 4) * index} x2={MAP_WIDTH} y2={(MAP_HEIGHT / 4) * index} />)}
          {features.map((feature) => {
            const [x, y] = projectCoordinate([feature.longitude, feature.latitude], viewport, MAP_WIDTH, MAP_HEIGHT);
            const active = selected?.id === feature.id;
            return (
              <g key={feature.id} className={`maps-marker ${active ? 'active' : ''}`} onClick={() => onSelect(feature.id)} tabIndex={0} role="button" aria-label={feature.label}>
                <circle cx={x} cy={y} r={active ? 11 : 8} />
                <text x={x + 12} y={y - 10}>{feature.label}</text>
              </g>
            );
          })}
          {!features.length ? <text className="maps-empty" x={MAP_WIDTH / 2} y={MAP_HEIGHT / 2} textAnchor="middle">Sin coordenadas para mostrar</text> : null}
        </svg>
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
  );
}
