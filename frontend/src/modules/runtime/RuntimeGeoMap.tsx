import { geometryViewport, projectCoordinate, unprojectCoordinate } from './geoEngine';
import type { Coordinate } from './geoEngine';

type Props = {
  coordinates: Coordinate[];
  closed: boolean;
  onAddCoordinate: (longitude: number, latitude: number) => void;
};

const WIDTH = 640;
const HEIGHT = 260;

export function RuntimeGeoMap({ coordinates, closed, onAddCoordinate }: Props) {
  const viewport = geometryViewport(coordinates);
  const projected = coordinates.map((coordinate) => projectCoordinate(coordinate, viewport, WIDTH, HEIGHT));
  const shapePoints = closed && projected.length >= 3 ? [...projected, projected[0]] : projected;
  const points = shapePoints.map(([x, y]) => `${x},${y}`).join(' ');

  function addFromMap(event: React.PointerEvent<SVGSVGElement>) {
    const bounds = event.currentTarget.getBoundingClientRect();
    const x = ((event.clientX - bounds.left) / bounds.width) * WIDTH;
    const y = ((event.clientY - bounds.top) / bounds.height) * HEIGHT;
    const [longitude, latitude] = unprojectCoordinate(x, y, viewport, WIDTH, HEIGHT);
    onAddCoordinate(longitude, latitude);
  }

  return (
    <svg className="runtime-geo-map" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Vista previa geografica; toque para agregar una coordenada" onPointerDown={addFromMap}>
      <rect width={WIDTH} height={HEIGHT} className="runtime-geo-map-background" />
      {[1, 2, 3, 4, 5].map((step) => <line key={`v-${step}`} x1={(WIDTH / 6) * step} y1={0} x2={(WIDTH / 6) * step} y2={HEIGHT} className="runtime-geo-grid" />)}
      {[1, 2, 3].map((step) => <line key={`h-${step}`} x1={0} y1={(HEIGHT / 4) * step} x2={WIDTH} y2={(HEIGHT / 4) * step} className="runtime-geo-grid" />)}
      {shapePoints.length > 1 ? <polyline points={points} className={closed ? 'runtime-geo-polygon' : 'runtime-geo-line'} /> : null}
      {projected.map(([x, y], index) => <g key={`${x}-${y}-${index}`}><circle cx={x} cy={y} r={6} className="runtime-geo-point" /><text x={x + 9} y={y - 8}>{index + 1}</text></g>)}
      {coordinates.length === 0 ? <text x={WIDTH / 2} y={HEIGHT / 2} textAnchor="middle" className="runtime-geo-empty">Toque para ubicar el primer punto</text> : null}
    </svg>
  );
}

