import { useEffect, useState } from 'react';
import { currentAccessToken } from '../modules/auth/session';
import * as autoSyncService from '../modules/offline/autoSyncService';
import { OFFLINE_QUEUE_CHANGED_EVENT, getPendingCount, purgeOldSynced, syncNow } from '../modules/offline/offlineSync';
import { useI18n } from '../i18n';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const REFRESH_INTERVAL_MS = 30000;

export function OfflineSyncStatus() {
  const { t } = useI18n();
  const [pending, setPending] = useState(0);
  const [message, setMessage] = useState('');
  const [syncing, setSyncing] = useState(false);
  const [autoStatus, setAutoStatus] = useState<autoSyncService.AutoSyncStatus>(autoSyncService.getStatus());

  const AUTO_SYNC_STATE_LABELS: Record<autoSyncService.AutoSyncState, string | null> = {
    idle: null,
    waiting: null,
    syncing: null,
    'paused-offline': t('offline.pausedOffline'),
    'paused-hidden': t('offline.pausedHidden'),
  };

  useEffect(() => {
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
      if (result.attempted) {
        const extra = result.failed ? t('offline.syncFailedExtra', { failed: result.failed }) : '';
        setMessage(t('offline.syncResult', { synced: result.synced, attempted: result.attempted, extra }));
      } else {
        setMessage('');
      }
      await refreshCount();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('offline.syncFailed'));
    } finally {
      setSyncing(false);
    }
  }

  async function cleanupOldSynced() {
    try {
      const purged = await purgeOldSynced();
      setMessage(purged ? t('offline.cleanupResult', { count: purged }) : t('offline.cleanupEmpty'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('offline.cleanupFailed'));
    }
  }

  const autoLabel = pending > 0 ? AUTO_SYNC_STATE_LABELS[autoStatus.state] : null;

  return (
    <div className="desktop-sync-status">
      {pending > 0 ? (
        <button className="secondary" onClick={() => void syncNowAndReport()} disabled={syncing}>
          {syncing ? t('offline.syncing') : t('offline.syncNow', { count: pending })}
        </button>
      ) : null}
      <button className="secondary" onClick={() => void cleanupOldSynced()}>{t('offline.cleanup')}</button>
      {autoLabel ? <small>{autoLabel}</small> : null}
      {message ? <span role="status">{message}</span> : null}
    </div>
  );
}
