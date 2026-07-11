const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';

export type EnrollmentValidation = { valid: boolean; project_id: string | null; user_id: string | null };

export async function validateEnrollmentQr(token: string, deviceFingerprint?: string): Promise<EnrollmentValidation> {
  const response = await fetch(`${API_BASE_URL}/enrollment/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, device_fingerprint: deviceFingerprint }),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new Error(body?.detail || 'Codigo QR invalido o vencido.');
  }
  return response.json();
}

/** Extrae el parametro `token` de la URL codificada en el QR del gestor. */
export function extractTokenFromScannedUrl(scannedText: string): string | null {
  try {
    const url = new URL(scannedText);
    return url.searchParams.get('token');
  } catch {
    return null;
  }
}
