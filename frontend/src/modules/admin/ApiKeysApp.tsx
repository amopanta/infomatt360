import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { createApiKey, fetchApiKeys, revokeApiKey } from './apiKeysApi';
import type { ApiKeyItem } from './apiKeysApi';

const DEFAULT_PERMISSIONS = [
  'records.read',
  'records.write',
  'reports.export',
  'gis.read',
  'messages.write',
];

export function ApiKeysApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [items, setItems] = useState<ApiKeyItem[]>([]);
  const [name, setName] = useState('');
  const [permissions, setPermissions] = useState('records.read');
  const [rateLimitProfile, setRateLimitProfile] = useState('standard');
  const [newKey, setNewKey] = useState('');
  const [message, setMessage] = useState('Cargando API keys...');

  useEffect(() => {
    fetchApiKeys(projectId)
      .then((rows) => { setItems(rows); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  async function submit() {
    try {
      const selected = permissions.split(',').map((item) => item.trim()).filter(Boolean);
      const created = await createApiKey({ projectId, name, permissions: selected, rateLimitProfile });
      setItems((current) => [created, ...current]);
      setNewKey(created.api_key);
      setName('');
      setMessage('API key creada. Copia el secreto ahora; no se volverá a mostrar.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear la API key.');
    }
  }

  async function revoke(keyId: string) {
    if (!window.confirm(`Vas a revocar la API key ${keyId}. Las integraciones que usen esta clave dejaran de funcionar. ¿Continuar?`)) return;
    try {
      const revoked = await revokeApiKey(projectId, keyId);
      setItems((current) => current.map((item) => item.key_id === keyId ? revoked : item));
      setMessage('API key revocada.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible revocar la API key.');
    }
  }

  return (
    <AppShell title="API keys">
      <main className="api-keys-shell">
        <section className="api-key-create">
          <h2>Nueva API key</h2>
          <p>Usa estas claves para integraciones externas. El secreto completo se muestra una sola vez.</p>
          <label>Nombre<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Integración externa" /></label>
          <label>
            Permisos
            <input value={permissions} onChange={(event) => setPermissions(event.target.value)} placeholder="records.read,reports.export" />
          </label>
          <label>
            Perfil de volumen
            <select value={rateLimitProfile} onChange={(event) => setRateLimitProfile(event.target.value)}>
              <option value="standard">Standard - integraciones normales</option>
              <option value="high_volume">Alto volumen - sincronizaciones grandes</option>
              <option value="trusted_sync">Trusted sync - sincronización confiable sin límite estricto</option>
            </select>
          </label>
          <div className="api-key-chips">
            {DEFAULT_PERMISSIONS.map((permission) => <button key={permission} onClick={() => setPermissions((current) => current.includes(permission) ? current : `${current ? `${current},` : ''}${permission}`)}>{permission}</button>)}
          </div>
          <button className="primary" disabled={!name.trim()} onClick={() => void submit()}>Crear API key</button>
          {newKey ? <div className="api-key-secret"><strong>Clave generada</strong><code>{newKey}</code><small>Cópiala ahora. Por seguridad no se volverá a mostrar.</small></div> : null}
          {message ? <p role="status">{message}</p> : null}
        </section>
        <section className="api-key-list">
          <h2>Claves del proyecto</h2>
          {items.length ? items.map((item) => (
            <article className={`api-key-card ${item.status}`} key={item.id}>
              <header>
                <div><strong>{item.name}</strong><small>{item.key_id} · {item.status} · {item.rate_limit_profile}</small></div>
                {item.status === 'active' ? <button onClick={() => void revoke(item.key_id)}>Revocar</button> : null}
              </header>
              <p>{item.permissions.join(', ') || 'Sin permisos asignados'}</p>
              <small>Creada: {item.created_at ? new Date(item.created_at).toLocaleString() : '—'} · Último uso: {item.last_used_at ? new Date(item.last_used_at).toLocaleString() : 'Nunca'}</small>
            </article>
          )) : <p>No hay API keys creadas.</p>}
        </section>
      </main>
    </AppShell>
  );
}
