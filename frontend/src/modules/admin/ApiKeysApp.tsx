import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
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
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [items, setItems] = useState<ApiKeyItem[]>([]);
  const [name, setName] = useState('');
  const [permissions, setPermissions] = useState('records.read');
  const [rateLimitProfile, setRateLimitProfile] = useState('standard');
  const [expiresInDays, setExpiresInDays] = useState('');
  const [newKey, setNewKey] = useState('');
  const [message, setMessage] = useState(t('admin.apiKeys.loading'));

  useEffect(() => {
    fetchApiKeys(projectId)
      .then((rows) => { setItems(rows); setMessage(''); })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  async function submit() {
    try {
      const selected = permissions.split(',').map((item) => item.trim()).filter(Boolean);
      const days = Number(expiresInDays);
      const expiresAt = expiresInDays.trim() && days > 0 ? new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString() : undefined;
      const created = await createApiKey({ projectId, name, permissions: selected, rateLimitProfile, expiresAt });
      setItems((current) => [created, ...current]);
      setNewKey(created.api_key);
      setName('');
      setExpiresInDays('');
      setMessage(t('admin.apiKeys.keyCreated'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.apiKeys.errorCreate'));
    }
  }

  async function revoke(keyId: string) {
    if (!window.confirm(t('admin.apiKeys.confirmRevoke', { keyId }))) return;
    try {
      const revoked = await revokeApiKey(projectId, keyId);
      setItems((current) => current.map((item) => item.key_id === keyId ? revoked : item));
      setMessage(t('admin.apiKeys.keyRevoked'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.apiKeys.errorRevoke'));
    }
  }

  return (
    <AppShell title={t('admin.apiKeys.title')}>
      <main className="api-keys-shell">
        <section className="api-key-create">
          <h2>{t('admin.apiKeys.newKeyTitle')}</h2>
          <p>{t('admin.apiKeys.newKeyDescription')}</p>
          <label>{t('admin.apiKeys.nameLabel')}<input value={name} onChange={(event) => setName(event.target.value)} placeholder={t('admin.apiKeys.namePlaceholder')} /></label>
          <label>
            {t('admin.apiKeys.permissionsLabel')}
            <input value={permissions} onChange={(event) => setPermissions(event.target.value)} placeholder="records.read,reports.export" />
          </label>
          <label>
            {t('admin.apiKeys.rateLimitLabel')}
            <select value={rateLimitProfile} onChange={(event) => setRateLimitProfile(event.target.value)}>
              <option value="standard">{t('admin.apiKeys.rateStandard')}</option>
              <option value="high_volume">{t('admin.apiKeys.rateHighVolume')}</option>
              <option value="trusted_sync">{t('admin.apiKeys.rateTrustedSync')}</option>
            </select>
          </label>
          <label>
            {t('admin.apiKeys.expiresInDays')}
            <input type="number" min="1" value={expiresInDays} onChange={(event) => setExpiresInDays(event.target.value)} placeholder={t('admin.apiKeys.noExpiration')} />
          </label>
          <div className="api-key-chips">
            {DEFAULT_PERMISSIONS.map((permission) => <button key={permission} onClick={() => setPermissions((current) => current.includes(permission) ? current : `${current ? `${current},` : ''}${permission}`)}>{permission}</button>)}
          </div>
          <button className="primary" disabled={!name.trim()} onClick={() => void submit()}>{t('admin.apiKeys.createKey')}</button>
          {newKey ? <div className="api-key-secret"><strong>{t('admin.apiKeys.generatedKey')}</strong><code>{newKey}</code><small>{t('admin.apiKeys.copyNow')}</small></div> : null}
          {message ? <p role="status">{message}</p> : null}
        </section>
        <section className="api-key-list">
          <h2>{t('admin.apiKeys.projectKeys')}</h2>
          {items.length ? items.map((item) => (
            <article className={`api-key-card ${item.status}`} key={item.id}>
              <header>
                <div><strong>{item.name}</strong><small>{item.key_id} · {item.status} · {item.rate_limit_profile}</small></div>
                {item.status === 'active' ? <button onClick={() => void revoke(item.key_id)}>{t('admin.apiKeys.revoke')}</button> : null}
              </header>
              <p>{item.permissions.join(', ') || t('admin.apiKeys.noPermissions')}</p>
              <small>{t('admin.apiKeys.createdLabel')}: {item.created_at ? new Date(item.created_at).toLocaleString() : '—'} · {t('admin.apiKeys.lastUsedLabel')}: {item.last_used_at ? new Date(item.last_used_at).toLocaleString() : t('admin.apiKeys.never')} · {t('admin.apiKeys.expiresLabel')}: {item.expires_at ? new Date(item.expires_at).toLocaleString() : t('admin.apiKeys.never')}</small>
            </article>
          )) : <p>{t('admin.apiKeys.noKeysYet')}</p>}
        </section>
      </main>
    </AppShell>
  );
}
