import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { authorizeGoogleDrive, connectS3Storage, fetchStorageProfiles } from './storageApi';
import type { StorageProfile } from './storageApi';

type Tab = 's3' | 'gdrive';

function providerLabel(provider: string) {
  const labels: Record<string, string> = { local: 'Disco local', s3: 'S3 / MinIO', gdrive: 'Google Drive' };
  return labels[provider] ?? provider;
}

export function StorageApp() {
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

  async function loadProfiles() {
    if (!projectId) return;
    try {
      setProfiles(await fetchStorageProfiles(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar los destinos de almacenamiento.');
    }
  }

  useEffect(() => { void loadProfiles(); }, [projectId]);

  async function submitConnectS3() {
    setConnecting(true);
    try {
      await connectS3Storage({ projectId, bucketName: bucketName.trim(), endpointUrl: endpointUrl.trim(), region: region.trim(), accessKeyId: accessKeyId.trim(), secretAccessKey });
      setMessage('Boveda S3/MinIO conectada. Las subidas de evidencias nuevas iran a este destino.');
      setBucketName('');
      setEndpointUrl('');
      setAccessKeyId('');
      setSecretAccessKey('');
      await loadProfiles();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible conectar la boveda S3/MinIO.');
    } finally {
      setConnecting(false);
    }
  }

  async function submitAuthorizeGdrive() {
    setAuthorizing(true);
    try {
      const { authorization_url: authorizationUrl } = await authorizeGoogleDrive(projectId);
      window.open(authorizationUrl, '_blank', 'noopener,noreferrer');
      setMessage('Se abrio una pestaña nueva para autorizar Google Drive. Al terminar, presiona "Actualizar lista" para ver el destino conectado.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible iniciar la autorizacion de Google Drive.');
    } finally {
      setAuthorizing(false);
    }
  }

  return (
    <AppShell title="Almacenamiento de multimedia">
      <main className="audit-shell">
        <nav className="erp-tabs">
          <button className={tab === 's3' ? 'active' : undefined} onClick={() => setTab('s3')}>S3 / MinIO</button>
          <button className={tab === 'gdrive' ? 'active' : undefined} onClick={() => setTab('gdrive')}>Google Drive</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 's3' ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>Conectar boveda S3/MinIO</h2>
                <p>Las fotos, audios y videos se convierten a WebP y se suben con hash SHA-256 (ver docs/89). Las credenciales se cifran; nunca se muestran despues de guardarlas.</p>
              </div>
            </header>
            <div className="ai-analyze-inline">
              <label>Bucket<input value={bucketName} onChange={(event) => setBucketName(event.target.value)} placeholder="infomatt360-evidencias" /></label>
              <label>Endpoint (opcional, MinIO)<input value={endpointUrl} onChange={(event) => setEndpointUrl(event.target.value)} placeholder="http://localhost:9000" /></label>
              <label>Region<input value={region} onChange={(event) => setRegion(event.target.value)} /></label>
              <label>Access key ID<input value={accessKeyId} onChange={(event) => setAccessKeyId(event.target.value)} /></label>
              <label>Secret access key<input type="password" value={secretAccessKey} onChange={(event) => setSecretAccessKey(event.target.value)} /></label>
              <button className="primary" disabled={connecting || !bucketName.trim() || !accessKeyId.trim() || !secretAccessKey} onClick={() => void submitConnectS3()}>
                {connecting ? 'Conectando…' : 'Conectar'}
              </button>
            </div>
          </section>
        ) : null}

        {tab === 'gdrive' ? (
          <section className="audit-panel">
            <header>
              <div>
                <h2>Conectar Google Drive</h2>
                <p>Abre una pestaña de Google para autorizar el acceso a una cuenta de Drive como destino de las evidencias del proyecto (ver docs/79).</p>
              </div>
              <button className="primary" disabled={authorizing} onClick={() => void submitAuthorizeGdrive()}>
                {authorizing ? 'Abriendo…' : 'Conectar Google Drive'}
              </button>
            </header>
          </section>
        ) : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>Destinos conectados</h2>
              <p>Solo el destino marcado como predeterminado por proveedor recibe subidas nuevas.</p>
            </div>
            <button onClick={() => void loadProfiles()}>Actualizar lista</button>
          </header>
          {!profiles.length ? <p>Aun no hay destinos de almacenamiento distintos al disco local para este proyecto.</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Proveedor</th>
                  <th>Bucket / ruta</th>
                  <th>Predeterminado</th>
                  <th>Estado</th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id}>
                    <td>{profile.name}</td>
                    <td>{providerLabel(profile.provider)}</td>
                    <td>{profile.bucket_name ?? profile.base_path ?? '—'}</td>
                    <td>{profile.is_default ? 'Si' : 'No'}</td>
                    <td>{profile.status}</td>
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
