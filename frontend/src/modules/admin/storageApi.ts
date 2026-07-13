export type StorageProfile = {
  id: string;
  project_id: string;
  name: string;
  provider: string;
  base_path?: string | null;
  bucket_name?: string | null;
  endpoint_url?: string | null;
  max_file_size_mb: number;
  is_default: boolean;
  status: string;
};

export type S3ConnectPayload = {
  projectId: string;
  name?: string;
  bucketName: string;
  endpointUrl?: string;
  region?: string;
  accessKeyId: string;
  secretAccessKey: string;
  isDefault?: boolean;
};

import { authorizationHeader } from '../auth/session';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

function headers(): HeadersInit {
  return { ...authorizationHeader(), 'Content-Type': 'application/json' };
}

async function parseOrThrow<T>(response: Response, fallbackMessage: string): Promise<T> {
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || fallbackMessage);
  }
  return response.json();
}

export async function fetchStorageProfiles(projectId: string): Promise<StorageProfile[]> {
  const response = await fetch(`${API_BASE_URL}/storage/project/${projectId}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible consultar los destinos de almacenamiento.');
}

export async function connectS3Storage(payload: S3ConnectPayload): Promise<StorageProfile> {
  const response = await fetch(`${API_BASE_URL}/storage/s3/connect`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({
      project_id: payload.projectId,
      name: payload.name || 'S3 / MinIO',
      bucket_name: payload.bucketName,
      endpoint_url: payload.endpointUrl || null,
      region: payload.region || 'us-east-1',
      access_key_id: payload.accessKeyId,
      secret_access_key: payload.secretAccessKey,
      is_default: payload.isDefault ?? true,
    }),
  });
  return parseOrThrow(response, 'No fue posible conectar la boveda S3/MinIO.');
}

export async function authorizeGoogleDrive(projectId: string): Promise<{ authorization_url: string }> {
  const response = await fetch(`${API_BASE_URL}/storage/oauth/gdrive/authorize?project_id=${encodeURIComponent(projectId)}`, { headers: headers() });
  return parseOrThrow(response, 'No fue posible iniciar la autorizacion de Google Drive.');
}
