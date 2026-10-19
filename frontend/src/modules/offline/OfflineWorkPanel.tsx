/** Panel "Trabajo sin conexión" del escritorio: PIN local y paquete descargado. */
import { useEffect, useState } from 'react';
import { useI18n } from '../../i18n';
import { hasOfflinePin, isValidPin, setOfflinePin } from '../auth/offlineSession';
import { isDesktopApp } from '../desktop/desktopBridge';
import { offlineCacheUser } from './offlineCache';
import { prepareOfflinePackage, readOfflinePackageMeta, type OfflinePackageMeta } from './offlinePackage';

/** Con red, el paquete se renueva solo si tiene más de 30 minutos. */
const AUTO_REFRESH_MS = 30 * 60 * 1000;

export function OfflineWorkPanel({ projectId, onDownloaded }: { projectId: string; onDownloaded?: () => void }) {
  const { t } = useI18n();
  const userId = offlineCacheUser();
  const [meta, setMeta] = useState<OfflinePackageMeta | null>(null);
  const [downloading, setDownloading] = useState(false);
  const [message, setMessage] = useState('');
  const [pinReady, setPinReady] = useState(() => Boolean(userId) && hasOfflinePin(userId));
  const [editingPin, setEditingPin] = useState(false);
  const [pin, setPin] = useState('');
  const [confirmation, setConfirmation] = useState('');

  async function download() {
    setDownloading(true);
    setMessage('');
    try {
      setMeta(await prepareOfflinePackage(projectId));
      onDownloaded?.();
    } catch (error) {
      setMessage(t('offlineDesktop.downloadFailed', { error: error instanceof TypeError ? t('offlineDesktop.needsConnection') : error instanceof Error ? error.message : String(error) }));
    } finally {
      setDownloading(false);
    }
  }

  useEffect(() => {
    if (!isDesktopApp() || !userId || !projectId) return;
    let active = true;
    void readOfflinePackageMeta(projectId).then((current) => {
      if (!active) return;
      setMeta(current);
      const stale = !current || Date.now() - Date.parse(current.downloadedAt) > AUTO_REFRESH_MS;
      if (stale && navigator.onLine !== false) void download();
    });
    return () => { active = false; };
  }, [projectId, userId]);

  if (!isDesktopApp() || !userId) return null;

  async function savePin() {
    if (!isValidPin(pin)) { setMessage(t('offlineDesktop.pinInvalid')); return; }
    if (pin !== confirmation) { setMessage(t('offlineDesktop.pinMismatch')); return; }
    await setOfflinePin(userId, pin);
    setPin(''); setConfirmation(''); setEditingPin(false); setPinReady(true);
    setMessage(t('offlineDesktop.pinSaved'));
  }

  return (
    <section className="offline-work-panel" aria-labelledby="offline-work-title">
      <h2 id="offline-work-title">{t('offlineDesktop.panelTitle')}</h2>
      <p>{t('offlineDesktop.panelDesc')}</p>
      <p className="offline-work-meta">{meta
        ? t('offlineDesktop.downloaded', { date: new Date(meta.downloadedAt).toLocaleString(), forms: meta.forms, participants: meta.participants })
        : t('offlineDesktop.notDownloaded')}</p>
      <button type="button" disabled={downloading} onClick={() => void download()}>{downloading ? t('offlineDesktop.downloading') : t('offlineDesktop.download')}</button>
      <p>{pinReady ? t('offlineDesktop.pinSet') : t('offlineDesktop.pinMissing')}</p>
      {pinReady && !editingPin
        ? <button type="button" className="secondary" onClick={() => setEditingPin(true)}>{t('offlineDesktop.changePin')}</button>
        : <form className="offline-work-pin" onSubmit={(event) => { event.preventDefault(); void savePin(); }}>
          <label>{t('offlineDesktop.pinLabel')}<input type="password" inputMode="numeric" autoComplete="new-password" maxLength={8} value={pin} onChange={(event) => setPin(event.target.value.replace(/\D/g, ''))} /></label>
          <label>{t('offlineDesktop.pinConfirm')}<input type="password" inputMode="numeric" autoComplete="new-password" maxLength={8} value={confirmation} onChange={(event) => setConfirmation(event.target.value.replace(/\D/g, ''))} /></label>
          <button type="submit">{t('offlineDesktop.savePin')}</button>
        </form>}
      {message ? <p role="status">{message}</p> : null}
    </section>
  );
}
