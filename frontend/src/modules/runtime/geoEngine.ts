export type Coordinate = [number, number];

export type RuntimeGeoValue =
  | { type: 'Point'; coordinates: Coordinate }
  | { type: 'LineString'; coordinates: Coordinate[] }
  | { type: 'Polygon'; coordinates: Coordinate[][] };

export type GeoViewport = {
  minLongitude: number;
  maxLongitude: number;
  minLatitude: number;
  maxLatitude: number;
};

export function isValidCoordinate(longitude: number, latitude: number): boolean {
  return Number.isFinite(longitude) && Number.isFinite(latitude)
    && longitude >= -180 && longitude <= 180
    && latitude >= -90 && latitude <= 90;
}

export function editableCoordinates(value?: RuntimeGeoValue | null): Coordinate[] {
  if (!value) return [];
  if (value.type === 'Point') return [value.coordinates];
  if (value.type === 'LineString') return value.coordinates;
  const ring = value.coordinates[0] ?? [];
  if (ring.length > 1 && ring[0][0] === ring[ring.length - 1][0] && ring[0][1] === ring[ring.length - 1][1]) return ring.slice(0, -1);
  return ring;
}

export function buildGeometry(type: 'GPS' | 'GEOTRACE' | 'GEOSHAPE', coordinates: Coordinate[]): RuntimeGeoValue | null {
  const valid = coordinates.filter(([longitude, latitude]) => isValidCoordinate(longitude, latitude));
  if (valid.length === 0) return null;
  if (type === 'GPS') return { type: 'Point', coordinates: valid[valid.length - 1] };
  if (type === 'GEOTRACE') return { type: 'LineString', coordinates: valid };
  const closed = valid.length >= 3 ? [...valid, valid[0]] : valid;
  return { type: 'Polygon', coordinates: [closed] };
}

export function minimumPoints(type: 'GPS' | 'GEOTRACE' | 'GEOSHAPE'): number {
  return type === 'GPS' ? 1 : type === 'GEOTRACE' ? 2 : 3;
}

export function geometryViewport(coordinates: Coordinate[]): GeoViewport {
  if (coordinates.length === 0) return { minLongitude: -180, maxLongitude: 180, minLatitude: -90, maxLatitude: 90 };
  const longitudes = coordinates.map((item) => item[0]);
  const latitudes = coordinates.map((item) => item[1]);
  const centerLongitude = (Math.min(...longitudes) + Math.max(...longitudes)) / 2;
  const centerLatitude = (Math.min(...latitudes) + Math.max(...latitudes)) / 2;
  const longitudeSpan = Math.max(0.02, Math.max(...longitudes) - Math.min(...longitudes));
  const latitudeSpan = Math.max(0.02, Math.max(...latitudes) - Math.min(...latitudes));
  const span = Math.max(longitudeSpan, latitudeSpan) * 1.35;
  return {
    minLongitude: Math.max(-180, centerLongitude - span / 2),
    maxLongitude: Math.min(180, centerLongitude + span / 2),
    minLatitude: Math.max(-90, centerLatitude - span / 2),
    maxLatitude: Math.min(90, centerLatitude + span / 2),
  };
}

export function projectCoordinate(coordinate: Coordinate, viewport: GeoViewport, width: number, height: number): [number, number] {
  const longitudeSpan = viewport.maxLongitude - viewport.minLongitude || 1;
  const latitudeSpan = viewport.maxLatitude - viewport.minLatitude || 1;
  return [
    ((coordinate[0] - viewport.minLongitude) / longitudeSpan) * width,
    height - ((coordinate[1] - viewport.minLatitude) / latitudeSpan) * height,
  ];
}

export function unprojectCoordinate(x: number, y: number, viewport: GeoViewport, width: number, height: number): Coordinate {
  return [
    viewport.minLongitude + (Math.max(0, Math.min(width, x)) / width) * (viewport.maxLongitude - viewport.minLongitude),
    viewport.minLatitude + ((height - Math.max(0, Math.min(height, y))) / height) * (viewport.maxLatitude - viewport.minLatitude),
  ];
}
