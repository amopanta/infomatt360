import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { authorizeGoogleDrive, configureGoogleDrive, connectS3Storage, fetchGoogleDriveStatus, fetchStorageProfiles, googleDriveCallbackUrl, selectDefaultStorage } from './storageApi';
import type { StorageProfile } from './storageApi';

type Tab = 's3' | 'gdrive';

export function StorageApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [tab, setTab] = useState<Tab>('s3');
  const [message, setMessage] = useState('');
  const [profiles, setProfiles] = useState<StorageProfile[]>([]);

  const [bucketName, setBucketName] = useState('');
  const [endpointUrl, setEndpointUrl] = useState('');
  const [region, setRegion] = useState('us-east-1');
  const [accessKeyId, setAccessKeyId] = useState('');
  const [secretAccessKey, setSecretAccessKey] = useState('');
  const [connecting, setConnecting] = useState(false);

  const [authorizing, setAuthorizing] = useState(false);
  const [selecting, setSelecting] = useState<string | null>(null);
  const [driveConfigured, setDriveConfigured] = useState(false);
  const [driveClientId, setDriveClientId] = useState('');
  const [driveClientSecret, setDriveClientSecret] = useState('');
  const [driveRedirectUri, setDriveRedirectUri] = useState(googleDriveCallbackUrl());
  const [savingDrive, setSavingDrive] = useState(false);

  function providerLabel(provider: string) {
    const labels: Record<string, string> = { local: t('admin.storage.providerLocal'), s3: t('admin.storage.providerS3'), gdrive: t('admin.storage.providerGdrive') };
    return labels[provider] ?? provider;
  }

  async function loadProfiles() {
    if (!projectId) return;
    try {
      setProfiles(await fetchStorageProfiles(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.storage.queryError'));
    }
  }

  useEffect(() => {
    void loadProfiles();
    if (projectId) void fetchGoogleDriveStatus(projectId).then(({ configured }) => setDriveConfigured(configured)).catch(() => setDriveConfigured(false));
  }, [projectId]);

  async function saveDriveConfig() {
    setSavingDrive(true);
    try {
      await configureGoogleDrive(projectId, driveClientId.trim(), driveClientSecret, driveRedirectUri.trim());
      setDriveConfigured(true);
      setDriveClientSecret('');
      await loadProfiles();
      setMessage(t('admin.storage.oauthSaved'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.storage.saveConfigError'));
    } finally {
      setSavingDrive(false);
    }
  }

  async function submitConnectS3() {
    setConnecting(true);
    try {
      await connectS3Storage({ projectId, bucketName: bucketName.trim(), endpointUrl: endpointUrl.trim(), region: region.trim(), accessKeyId: accessKeyId.trim(), secretAccessKey });
      setMessage(t('admin.storage.s3Connected'));
      setBucketName('');
      setEndpointUrl('');
      setAccessKeyId('');
      setSecretAccessKey('');
      await loadProfiles();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.storage.s3ConnectError'));
    } finally {
      setConnecting(false);
    }
  }

  async function submitAuthorizeGdrive() {
    setAuthorizing(true);
    const popup = window.open('', '_blank');
    try {
      const { authorization_url: authorizationUrl } = await authorizeGoogleDrive(projectId);
      if (popup) popup.location.href = authorizationUrl;
      else window.location.assign(authorizationUrl);
      setMessage(t('admin.storage.gdriveAuthorizeHint'));
    } catch (error) {
      popup?.close();
      setMessage(error instanceof Error ? error.message : t('admin.storage.gdriveAuthorizeError'));
    } finally {
      setAuthorizing(false);
    }
  }

  async function chooseDefault(profile: StorageProfile) {
    setSelecting(profile.id);
    try {
      await selectDefaultStorage(projectId, profile.id);
      await loadProfiles();
      setMessage(t('admin.storage.defaultChanged', { provider: providerLabel(profile.provider) }));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.storage.changeDefaultError'));
    } finally {
      setSelecting(null);
    }
  }

  return (
    <AppShell title={t('admin.storage.title')}>
      <main className="audit-shell">
        <nav className="erp-tabs">
          <button className={tab === 's3' ? 'active' : undefined} onClick={() => setTab('s3')}>{t('admin.storage.providerS3')}</button>
          <button className={tab === 'gdrive' ? 'active' : undefined} onClick={() => setTab('gdrive')}>{t('admin.storage.providerGdrive')}</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 's3' ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>{t('admin.storage.s3Title')}</h2>
                <p>{t('admin.storage.s3Description')}</p>
              </div>
            </header>
            <div className="ai-analyze-inline">
              <label>{t('admin.storage.bucketLabel')}<input value={bucketName} onChange={(event) => setBucketName(event.target.value)} placeholder={t('admin.storage.bucketPlaceholder')} /></label>
              <label>{t('admin.storage.endpointLabel')}<input value={endpointUrl} onChange={(event) => setEndpointUrl(event.target.value)} placeholder={t('admin.storage.endpointPlaceholder')} /></label>
              <label>{t('admin.storage.regionLabel')}<input value={region} onChange={(event) => setRegion(event.target.value)} /></label>
              <label>{t('admin.storage.accessKeyLabel')}<input value={accessKeyId} onChange={(event) => setAccessKeyId(event.target.value)} /></label>
              <label>{t('admin.storage.secretKeyLabel')}<input type="password" value={secretAccessKey} onChange={(event) => setSecretAccessKey(event.target.value)} /></label>
              <button className="primary" disabled={connecting || !bucketName.trim() || !accessKeyId.trim() || !secretAccessKey} onClick={() => void submitConnectS3()}>
                {connecting ? t('admin.storage.connecting') : t('admin.storage.connect')}
              </button>
            </div>
          </section>
        ) : null}

        {tab === 'gdrive' ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>{t('admin.storage.gdriveTitle')}</h2>
                <p>{t('admin.storage.gdriveDescription')}</p>
              </div>
              <button className="primary" disabled={authorizing || !driveConfigured} onClick={() => void submitAuthorizeGdrive()}>
                {authorizing ? t('admin.storage.opening') : t('admin.storage.gdriveConnect')}
              </button>
            </header>
            <p role="status">{driveConfigured ? t('admin.storage.oauthConfigured') : t('admin.storage.oauthMissing')}</p>
            <div className="ai-analyze-inline">
              <label>{t('admin.storage.clientIdLabel')}<input value={driveClientId} onChange={(event) => setDriveClientId(event.target.value)} placeholder={t('admin.storage.clientIdPlaceholder')} autoComplete="off" /></label>
              <label>{t('admin.storage.clientSecretLabel')}<input type="password" value={driveClientSecret} onChange={(event) => setDriveClientSecret(event.target.value)} placeholder={t('admin.storage.secretPlaceholder')} autoComplete="new-password" /></label>
              <label>{t('admin.storage.redirectUriLabel')}<input value={driveRedirectUri} onChange={(event) => setDriveRedirectUri(event.target.value)} /></label>
              <button disabled={savingDrive || !driveClientId.trim() || !driveClientSecret.trim() || !driveRedirectUri.trim()} onClick={() => void saveDriveConfig()}>{savingDrive ? t('admin.storage.saving') : t('admin.storage.saveOAuth')}</button>
            </div>
            <small>{t('admin.storage.redirectHint')}</small>
          </section>
        ) : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>{t('admin.storage.connectedTitle')}</h2>
              <p>{t('admin.storage.connectedDescription')}</p>
            </div>
            <button onClick={() => void loadProfiles()}>{t('admin.storage.refreshList')}</button>
          </header>
          {!profiles.length ? <p>{t('admin.storage.noProfiles')}</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>{t('admin.storage.nameColumn')}</th>
                  <th>{t('admin.storage.providerColumn')}</th>
                  <th>{t('admin.storage.bucketPathColumn')}</th>
                  <th>{t('admin.storage.defaultColumn')}</th>
                  <th>{t('admin.storage.statusColumn')}</th>
                  <th>{t('admin.storage.actionColumn')}</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id}>
                    <td>{profile.name}</td>
                    <td>{providerLabel(profile.provider)}</td>
                    <td>{profile.bucket_name ?? profile.base_path ?? '—'}</td>
                    <td>{profile.is_default ? t('admin.storage.yes') : t('admin.storage.no')}</td>
                    <td>{profile.connected === false ? t('admin.storage.pendingConnection') : profile.status}</td>
                    <td>{profile.is_default ? t('admin.storage.inUse') : <button disabled={selecting === profile.id || profile.status !== 'active' || profile.connected === false} onClick={() => void chooseDefault(profile)}>{selecting === profile.id ? t('admin.storage.activating') : t('admin.storage.useForUploads')}</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
