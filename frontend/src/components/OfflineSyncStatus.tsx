import { useEffect, useState } from 'react';
import { currentAccessToken } from '../modules/auth/session';
import { OFFLINE_QUEUE_CHANGED_EVENT, getPendingCount, syncNow } from '../modules/offline/offlineSync';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const REFRESH_INTERVAL_MS = 30000;

export function OfflineSyncStatus() {
  const [pending, setPending] = useState(0);
  const [message, setMessage] = useState('');
  const [syncing, setSyncing] = useState(false);

  useEffect(() => {
    void refreshCount();
    const timer = window.setInterval(() => void refreshCount(), REFRESH_INTERVAL_MS);
    const onQueueChanged = () => void refreshCount();
    window.addEventListener('online', refreshAndSync);
    window.addEventListener(OFFLINE_QUEUE_CHANGED_EVENT, onQueueChanged);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener('online', refreshAndSync);
      window.removeEventListener(OFFLINE_QUEUE_CHANGED_EVENT, onQueueChanged);
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

  if (pending === 0 && !message) return null;

  return (
    <div className="desktop-sync-status">
      <button className="secondary" onClick={() => void syncNowAndReport()} disabled={syncing || pending === 0}>
        {syncing ? 'Sincronizando...' : `Sincronizar pendientes (${pending})`}
      </button>
      {message ? <span role="status">{message}</span> : null}
    </div>
  );
}
