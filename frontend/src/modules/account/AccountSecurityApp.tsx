import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { clearStoredSession } from '../auth/session';
import { confirmMfa, disableMfa, fetchMfaStatus, setupMfa } from './api';
import { useI18n } from '../../i18n';

export function AccountSecurityApp() {
  const { t } = useI18n();
  const [enabled, setEnabled] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [secret, setSecret] = useState('');
  const [uri, setUri] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [message, setMessage] = useState(t('account.loadingSecurity'));

  useEffect(() => { fetchMfaStatus().then((status) => { setEnabled(status.enabled); setRemaining(status.recovery_codes_remaining); setMessage(''); }).catch((error: Error) => setMessage(error.message)); }, []);

  async function beginSetup() {
    try { const result = await setupMfa(password); setSecret(result.secret); setUri(result.provisioning_uri); setPassword(''); setMessage(t('account.addToAuthApp')); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Error.'); }
  }
  async function confirm() {
    try { const result = await confirmMfa(code); setRecoveryCodes(result.recovery_codes); setEnabled(true); setCode(''); setMessage(result.message); }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Error.'); }
  }
  async function disable() {
    try { await disableMfa(password, code); clearStoredSession(); window.location.href = '/'; }
    catch (error) { setMessage(error instanceof Error ? error.message : 'Error.'); }
  }

  return <AppShell title={t('account.securityTitle')}><main className="admin-users"><section className="admin-user-card"><h2>{t('account.twoStepVerification')}</h2><p>{enabled ? t('account.mfaActive', { remaining }) : t('account.mfaInactive')}</p>{message ? <p role="status">{message}</p> : null}{recoveryCodes.length ? <><h3>{t('account.saveCodesNow')}</h3><p>{t('account.codesOneTime')}</p><pre>{recoveryCodes.join('\n')}</pre><button onClick={() => { clearStoredSession(); window.location.href = '/'; }}>{t('account.codesSaved')}</button></> : enabled ? <><label>{t('account.yourPassword')}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>{t('account.mfaOrRecoveryCode')}<input value={code} onChange={(event) => setCode(event.target.value.trim())} /></label><button onClick={() => void disable()}>{t('account.disableMfa')}</button></> : secret ? <><p><strong>{t('account.manualKey')}</strong> <code>{secret}</code></p><details><summary>{t('account.configUri')}</summary><code>{uri}</code></details><label>{t('account.sixDigitCode')}<input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value.trim())} /></label><button onClick={() => void confirm()}>{t('account.confirmAndActivate')}</button></> : <><label>{t('account.confirmPassword')}<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><button onClick={() => void beginSetup()}>{t('account.setupMfa')}</button></>}</section></main></AppShell>;
}
