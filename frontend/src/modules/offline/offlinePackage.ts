/**
 * Paquete sin conexión del escritorio: baja de una vez lo que el gestor
 * necesita para capturar sin internet (mismo alcance que la app móvil,
 * docs/141 §3). Las consultas pasan por `cachedJson`, así que el paquete
 * es la misma copia que luego usan las pantallas cuando falla la red.
 */

import { fetchMyFormAssignments, fetchOpenForms } from '../builder/myFormsApi';
import { fetchParticipantHistory } from '../participants/api';
import { fetchCaptureParticipants, fetchRuntimeTemplate } from '../runtime/api';
import { offlineCacheEnabled, readCache, writeCache } from './offlineCache';

/** Igual que la app móvil: historial de hasta 300 participantes. */
export const MAX_HISTORY_PARTICIPANTS = 300;

export type OfflinePackageMeta = { downloadedAt: string; forms: number; participants: number; failedForms: number };

const metaKey = (projectId: string) => `package-meta:${projectId}`;

export async function readOfflinePackageMeta(projectId: string): Promise<OfflinePackageMeta | null> {
  return (await readCache<OfflinePackageMeta>(metaKey(projectId)).catch(() => null))?.value ?? null;
}

export async function prepareOfflinePackage(projectId: string): Promise<OfflinePackageMeta> {
  if (!offlineCacheEnabled()) throw new Error('Disponible solo en la app de escritorio.');
  if (typeof navigator !== 'undefined' && navigator.onLine === false) throw new TypeError('Sin conexión');
  const [assignments, openForms] = await Promise.all([fetchMyFormAssignments(projectId), fetchOpenForms(projectId)]);
  const templateIds = [...new Set([...assignments.map((row) => row.template_id), ...openForms.map((form) => form.id)])];
  let failedForms = 0;
  for (const templateId of templateIds) {
    // Un formulario que ya no se puede abrir no impide bajar los demás.
    try {
      await fetchRuntimeTemplate(templateId);
      await fetchCaptureParticipants(templateId);
    } catch {
      failedForms += 1;
    }
  }
  const participantIds = [...new Set(assignments.map((row) => row.participant_id))];
  for (const participantId of participantIds.slice(0, MAX_HISTORY_PARTICIPANTS)) {
    await fetchParticipantHistory(participantId).catch(() => undefined);
  }
  const meta: OfflinePackageMeta = { downloadedAt: new Date().toISOString(), forms: templateIds.length - failedForms, participants: participantIds.length, failedForms };
  await writeCache(metaKey(projectId), meta);
  return meta;
}

type CachedCapture = Awaited<ReturnType<typeof fetchCaptureParticipants>>;
type CachedAssignments = Awaited<ReturnType<typeof fetchMyFormAssignments>>;

/**
 * Tras guardar sin red, marca la actividad como aplicada en la copia local
 * para que el mismo participante no se capture dos veces antes de
 * sincronizar. Al reconectar, la copia se reemplaza con la del servidor.
 */
export async function markCapturedOffline(projectId: string, templateId: string, participantId: string): Promise<void> {
  if (!offlineCacheEnabled()) return;
  const captureKey = `capture-participants:${templateId}`;
  const capture = await readCache<CachedCapture>(captureKey);
  if (capture) {
    const assignments = capture.value.assignments.map((row) => row.participant_id === participantId ? { ...row, status: 'completed' as const } : row);
    await writeCache(captureKey, { ...capture.value, assignments });
  }
  const mineKey = `my-assignments:${projectId}`;
  const mine = await readCache<CachedAssignments>(mineKey);
  if (mine) {
    await writeCache(mineKey, mine.value.map((row) => row.template_id === templateId && row.participant_id === participantId ? { ...row, assignment_status: 'completed' } : row));
  }
}
