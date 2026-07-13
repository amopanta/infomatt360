import { useEffect, useState } from 'react';

import { BrandLogo } from '../../components/BrandLogo';
import { EnrollScanApp } from '../enrollment/EnrollScanApp';
import { InstallWizardApp } from '../install/InstallWizardApp';
import { PublicFormApp } from '../publicform/PublicFormApp';
import { changePassword, fetchSession, login, logout, refreshAccessToken, requestPasswordReset, resetPassword, verifyMfa } from './api';
import { clearStoredSession, currentAccessToken, PROJECT_KEY, setAccessToken, storeSelectedProjectPermissions, storeSessionProjects, validSelectedProject } from './session';
import type { AuthSession } from './types';

type Props = { children: React.ReactNode };

export function AuthGate({ children }: Props) {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [mfaChallenge, setMfaChallenge] = useState('');
  const resetToken = new URLSearchParams(window.location.search).get('token');

  async function closeSession() {
    try { await logout(); }
    finally { clearStoredSession(); setSession(null); }
  }

  async function loadSession(token: string) {
    try {
      const nextSession = await fetchSession(token);
      storeSessionProjects(nextSession.projects);
      const projectId = validSelectedProject(nextSession.projects, localStorage.getItem(PROJECT_KEY));
      if (projectId) {
        localStorage.setItem(PROJECT_KEY, projectId);
        storeSelectedProjectPermissions(nextSession.projects, projectId);
      } else {
        localStorage.removeItem(PROJECT_KEY);
        storeSelectedProjectPermissions(nextSession.projects, null);
      }
      setSession(nextSession);
    } catch (reason) {
      clearStoredSession();
      setError(reason instanceof Error ? reason.message : 'No fue posible validar la sesión.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void refreshAccessToken()
      .then((token) => loadSession(token))
      .catch(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!session) return undefined;
    const timer = window.setInterval(() => {
      void refreshAccessToken().catch(() => {
        clearStoredSession();
        setSession(null);
        setError('La sesión expiró. Inicia sesión nuevamente.');
      });
    }, 50 * 60 * 1000);
    return () => window.clearInterval(timer);
  }, [session]);

  if (window.location.pathname === '/reset-password' && resetToken) return <ResetPasswordPanel token={resetToken} />;
  if (window.location.pathname === '/install') return <InstallWizardApp />;
  if (window.location.pathname === '/enroll') return <EnrollScanApp />;
  if (window.location.pathname.startsWith('/public-form/')) return <PublicFormApp />;

  async function submitLogin(email: string, password: string) {
    setError('');
    setLoading(true);
    try {
      const tokens = await login(email, password);
      if (tokens.mfa_required && tokens.mfa_challenge_token) {
        setMfaChallenge(tokens.mfa_challenge_token);
        setLoading(false);
        return;
      }
      if (!tokens.access_token) throw new Error('Respuesta de autenticación incompleta.');
      setAccessToken(tokens.access_token);
      await loadSession(tokens.access_token);
    } catch (reason) {
      setLoading(false);
      setError(reason instanceof Error ? reason.message : 'No fue posible iniciar sesión.');
    }
  }

  async function submitMfa(code: string) {
    setError('');
    try {
      const tokens = await verifyMfa(mfaChallenge, code);
      setAccessToken(tokens.access_token);
      setMfaChallenge('');
      await loadSession(tokens.access_token);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : 'No fue posible validar el segundo factor.');
    }
  }

  if (loading) return <div className="auth-page"><p>Validando sesión...</p></div>;
  if (!session && mfaChallenge) return <MfaPanel error={error} onSubmit={submitMfa} onCancel={() => { setMfaChallenge(''); setError(''); }} />;
  if (!session) return <LoginPanel error={error} onSubmit={submitLogin} />;

  if (session.must_change_password) {
    return <ChangePasswordPanel token={currentAccessToken()} onComplete={() => { clearStoredSession(); setSession(null); setError('Contraseña actualizada. Inicia sesión nuevamente.'); }} />;
  }

  const selectedProject = validSelectedProject(session.projects, localStorage.getItem(PROJECT_KEY));
  if (!selectedProject) {
    return (
      <div className="auth-page">
        <div className="auth-card">
          <BrandLogo />
          <h1>Selecciona un proyecto</h1>
          {session.projects.length === 0 ? <p>No tienes proyectos activos asignados.</p> : session.projects.map((project) => (
            <button key={project.id} onClick={() => { localStorage.setItem(PROJECT_KEY, project.id); storeSelectedProjectPermissions(session.projects, project.id); setSession({ ...session }); }}>{project.name}</button>
          ))}
          <button className="secondary" onClick={() => void closeSession()}>Cerrar sesión</button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}

function MfaPanel({ error, onSubmit, onCancel }: { error: string; onSubmit: (code: string) => Promise<void>; onCancel: () => void }) {
  const [code, setCode] = useState('');
  return <div className="auth-page"><form className="auth-card" onSubmit={(event) => { event.preventDefault(); void onSubmit(code); }}><BrandLogo /><h1>Verificación en dos pasos</h1><p>Escribe el código de tu aplicación o uno de recuperación.</p><label>Código<input required autoComplete="one-time-code" value={code} onChange={(event) => setCode(event.target.value.trim())} /></label>{error ? <p role="alert">{error}</p> : null}<button type="submit">Verificar</button><button className="secondary" type="button" onClick={onCancel}>Cancelar</button></form></div>;
}

function LoginPanel({ error, onSubmit }: { error: string; onSubmit: (email: string, password: string) => Promise<void> }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [recoveryMessage, setRecoveryMessage] = useState('');
  async function recover() {
    if (!email) { setRecoveryMessage('Escribe primero tu correo.'); return; }
    try { setRecoveryMessage(await requestPasswordReset(email)); } catch (reason) { setRecoveryMessage(reason instanceof Error ? reason.message : 'No fue posible procesar la solicitud.'); }
  }
  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={(event) => { event.preventDefault(); void onSubmit(email, password); }}>
        <BrandLogo />
        <h1>Iniciar sesión</h1>
        <label>Correo<input type="email" required autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} /></label>
        <label>Contraseña<input type="password" required minLength={6} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
        {error ? <p role="alert">{error}</p> : null}
        <button type="submit">Ingresar</button>
        <button className="secondary" type="button" onClick={() => void recover()}>Olvidé mi contraseña</button>
        {recoveryMessage ? <p role="status">{recoveryMessage}</p> : null}
      </form>
    </div>
  );
}

function PasswordFields({ currentPassword, setCurrentPassword, newPassword, setNewPassword, confirmation, setConfirmation, includeCurrent = true }: { currentPassword: string; setCurrentPassword: (value: string) => void; newPassword: string; setNewPassword: (value: string) => void; confirmation: string; setConfirmation: (value: string) => void; includeCurrent?: boolean }) {
  return <>{includeCurrent ? <label>Contraseña actual<input type="password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} /></label> : null}<label>Nueva contraseña<input type="password" required minLength={15} maxLength={72} value={newPassword} onChange={(event) => setNewPassword(event.target.value)} /><small>Mínimo 15 caracteres; se permiten frases y espacios.</small></label><label>Confirmar contraseña<input type="password" required minLength={15} maxLength={72} value={confirmation} onChange={(event) => setConfirmation(event.target.value)} /></label></>;
}

function ChangePasswordPanel({ token, onComplete }: { token: string; onComplete: () => void }) {
  const [current, setCurrent] = useState(''); const [next, setNext] = useState(''); const [confirmation, setConfirmation] = useState(''); const [message, setMessage] = useState('Debes reemplazar la contraseña temporal antes de continuar.');
  async function submit(event: React.FormEvent) { event.preventDefault(); try { await changePassword(token, current, next, confirmation); onComplete(); } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'No fue posible cambiarla.'); } }
  return <div className="auth-page"><form className="auth-card" onSubmit={(event) => void submit(event)}><BrandLogo /><h1>Cambiar contraseña</h1><p>{message}</p><PasswordFields currentPassword={current} setCurrentPassword={setCurrent} newPassword={next} setNewPassword={setNext} confirmation={confirmation} setConfirmation={setConfirmation} /><button type="submit">Guardar nueva contraseña</button></form></div>;
}

function ResetPasswordPanel({ token }: { token: string }) {
  const [next, setNext] = useState(''); const [confirmation, setConfirmation] = useState(''); const [message, setMessage] = useState('');
  async function submit(event: React.FormEvent) { event.preventDefault(); try { setMessage(await resetPassword(token, next, confirmation)); } catch (reason) { setMessage(reason instanceof Error ? reason.message : 'No fue posible restablecerla.'); } }
  return <div className="auth-page"><form className="auth-card" onSubmit={(event) => void submit(event)}><BrandLogo /><h1>Restablecer contraseña</h1><PasswordFields currentPassword="" setCurrentPassword={() => undefined} newPassword={next} setNewPassword={setNext} confirmation={confirmation} setConfirmation={setConfirmation} includeCurrent={false} />{message ? <p role="status">{message}</p> : null}<button type="submit">Restablecer</button><a href="/">Volver al ingreso</a></form></div>;
}
