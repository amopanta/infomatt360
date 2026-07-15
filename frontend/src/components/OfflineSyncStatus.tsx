import { useEffect, useState } from 'react';
import { currentAccessToken } from '../modules/auth/session';
import * as autoSyncService from '../modules/offline/autoSyncService';
import { OFFLINE_QUEUE_CHANGED_EVENT, getPendingCount, purgeOldSynced, syncNow } from '../modules/offline/offlineSync';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const REFRESH_INTERVAL_MS = 30000;

const AUTO_SYNC_STATE_LABELS: Record<autoSyncService.AutoSyncState, string | null> = {
  idle: null,
  waiting: null,
  syncing: null,
  'paused-offline': 'Pausado (sin conexión)',
  'paused-hidden': 'Pausado (pestaña en segundo plano)',
};

export function OfflineSyncStatus() {
  const [pending, setPending] = useState(0);
  const [message, setMessage] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [autoStatus, setAutoStatus] = useState<autoSyncService.AutoSyncStatus>(autoSyncService.getStatus());

  useEffect(() => {
    // Reintento automatico en segundo plano (ver docs/107, hallazgo
    // SYNC-003) -- ensureStarted() es idempotente, seguro de llamar en
    // cada montaje aunque este componente se vuelva a montar en cada
    // navegacion (este proyecto no tiene un layout persistente).
    autoSyncService.ensureStarted(API_BASE_URL);

    void refreshCount();
    const timer = window.setInterval(() => void refreshCount(), REFRESH_INTERVAL_MS);
    const onQueueChanged = () => void refreshCount();
    const onAutoSyncStatusChanged = () => setAutoStatus(autoSyncService.getStatus());
    window.addEventListener('online', refreshAndSync);
    window.addEventListener(OFFLINE_QUEUE_CHANGED_EVENT, onQueueChanged);
    window.addEventListener(autoSyncService.AUTO_SYNC_STATUS_CHANGED_EVENT, onAutoSyncStatusChanged);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('online', refreshAndSync);
      window.removeEventListener(OFFLINE_QUEUE_CHANGED_EVENT, onQueueChanged);
      window.removeEventListener(autoSyncService.AUTO_SYNC_STATUS_CHANGED_EVENT, onAutoSyncStatusChanged);
    };
  }, []);

  async function refreshCount() {
    setPending(await getPendingCount());
  }

  function refreshAndSync() {
    void syncNowAndReport();
  }

  async function syncNowAndReport() {
    setSyncing(true);
    setMessage('');
    try {
      const result = await syncNow({ apiBaseUrl: API_BASE_URL, accessToken: currentAccessToken() });
      const extra = result.failed ? `, ${result.failed} con error` : '';
      setMessage(result.attempted ? `Sincronizados ${result.synced} de ${result.attempted}${extra}.` : '');
      await refreshCount();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible sincronizar.');
    } finally {
      setSyncing(false);
    }
  }

  async function cleanupOldSynced() {
    try {
      const purged = await purgeOldSynced();
      setMessage(purged ? `${purged} registro(s) sincronizado(s) antiguo(s) eliminado(s) del dispositivo.` : 'No había registros sincronizados con más de 7 días.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible limpiar la cola local.');
    }
  }

  const autoLabel = pending > 0 ? AUTO_SYNC_STATE_LABELS[autoStatus.state] : null;

  return (
    <div className="desktop-sync-status">
      {pending > 0 ? (
        <button className="secondary" onClick={() => void syncNowAndReport()} disabled={syncing}>
          {syncing ? 'Sincronizando...' : `Sincronizar pendientes (${pending})`}
        </button>
      ) : null}
      {/* El botón de limpieza queda disponible aunque no haya nada pendiente
          -- la purga automática (ver docs/107, SYNC-005) solo corre como
          parte de un `syncNow()` exitoso, así que si no hay nada pendiente
          hace días, este es el único disparador que le queda al usuario
          para liberar espacio antes de que se cumplan los 7 días. */}
      <button className="secondary" onClick={() => void cleanupOldSynced()}>Limpiar sincronizados antiguos</button>
      {autoLabel ? <small>{autoLabel}</small> : null}
      {message ? <span role="status">{message}</span> : null}
    </div>
  );
}
