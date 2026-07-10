import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { clearStoredSession } from '../auth/session';
import { confirmMfa, disableMfa, fetchMfaStatus, setupMfa } from './api';

export function AccountSecurityApp() {
  const [enabled, setEnabled] = useState(false);
  const [remaining, setRemaining] = useState(0);
  const [password, setPassword] = useState('');
  const [code, setCode] = useState('');
  const [secret, setSecret] = useState('');
  const [uri, setUri] = useState('');
  const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
  const [message, setMessage] = useState('Cargando seguridad...');

  useEffect(() => { fetchMfaStatus().then((status) => { setEnabled(status.enabled); setRemaining(status.recovery_codes_remaining); setMessage(''); }).catch((error: Error) => setMessage(error.message)); }, []);

  async function beginSetup() {
    try { const result = await setupMfa(password); setSecret(result.secret); setUri(result.provisioning_uri); setPassword(''); setMessage('Agrega la cuenta en tu aplicación autenticadora y confirma el código.'); }
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

  return <AppShell title="Seguridad de mi cuenta"><main className="admin-users"><section className="admin-user-card"><h2>Verificación en dos pasos</h2><p>{enabled ? `MFA activo. Códigos de recuperación restantes: ${remaining}` : 'MFA está desactivado.'}</p>{message ? <p role="status">{message}</p> : null}{recoveryCodes.length ? <><h3>Guarda estos códigos ahora</h3><p>Cada uno funciona una sola vez y no volverá a mostrarse.</p><pre>{recoveryCodes.join('\n')}</pre><button onClick={() => { clearStoredSession(); window.location.href = '/'; }}>Ya los guardé; iniciar nuevamente</button></> : enabled ? <><label>Tu contraseña<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><label>Código MFA o de recuperación<input value={code} onChange={(event) => setCode(event.target.value.trim())} /></label><button onClick={() => void disable()}>Desactivar MFA</button></> : secret ? <><p><strong>Clave manual:</strong> <code>{secret}</code></p><details><summary>URI de configuración</summary><code>{uri}</code></details><label>Código de seis dígitos<input inputMode="numeric" autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value.trim())} /></label><button onClick={() => void confirm()}>Confirmar y activar</button></> : <><label>Confirma tu contraseña<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label><button onClick={() => void beginSetup()}>Configurar MFA</button></>}</section></main></AppShell>;
}
