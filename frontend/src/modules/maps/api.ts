export type MapFeature = {
  id: string;
  project_id: string;
  source: 'gis' | 'runtime';
  feature_type: 'Point' | 'LineString' | 'Polygon';
  latitude: number;
  longitude: number;
  label: string;
  template_id?: string | null;
  template_name?: string | null;
  record_id?: string | null;
  field_name?: string | null;
  geometry_json?: string | null;
  properties_json?: string | null;
};

export type ProjectMap = {
  project_id: string;
  features: MapFeature[];
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export async function fetchProjectMap(projectId: string): Promise<ProjectMap> {
  const response = await fetch(`${API_BASE_URL}/gis/map/${projectId}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible cargar el mapa del proyecto.');
  return response.json();
}

export async function fetchNearbyFeatures(projectId: string, lat: number, lng: number, radiusKm: number): Promise<MapFeature[]> {
  const params = new URLSearchParams({ lat: String(lat), lng: String(lng), radius_km: String(radiusKm) });
  const response = await fetch(`${API_BASE_URL}/gis/features/${projectId}/nearby?${params}`, { headers: authorizationHeader() });
  if (!response.ok) throw new Error('No fue posible buscar elementos cercanos.');
  return response.json();
}
