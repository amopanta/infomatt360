import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchAdminUsers, generateEnrollmentQr, resetUserMfa, resetUserPassword, updateUserEmail } from './api';
import type { AdminUser } from './api';

export function AdminUserSecurityApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [message, setMessage] = useState('Cargando usuarios...');

  useEffect(() => {
    fetchAdminUsers(projectId)
      .then((rows) => {
        setUsers(rows);
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  return (
    <AppShell title="Seguridad de usuarios">
      <main className="admin-users">
        <h2>Usuarios del proyecto</h2>
        <p>Las operaciones sensibles requieren tu contrasena administrativa, piden confirmacion y quedan auditadas.</p>
        {message ? <p role="status">{message}</p> : null}
        {users.map((user) => (
          <AdminUserCard
            key={user.id}
            projectId={projectId}
            user={user}
            onUpdated={(next) => setUsers((current) => current.map((item) => item.id === next.id ? next : item))}
          />
        ))}
      </main>
    </AppShell>
  );
}

function AdminUserCard({ projectId, user, onUpdated }: { projectId: string; user: AdminUser; onUpdated: (user: AdminUser) => void }) {
  const [email, setEmail] = useState(user.email);
  const [adminPassword, setAdminPassword] = useState('');
  const [temporary, setTemporary] = useState('');
  const [result, setResult] = useState('');
  const [qrImageUrl, setQrImageUrl] = useState('');

  async function changeEmail() {
    if (!window.confirm(`Vas a cambiar el correo de ${user.email} a ${email}. ¿Continuar?`)) return;
    try {
      const next = await updateUserEmail(projectId, user.id, email, adminPassword);
      onUpdated(next);
      setResult('Correo actualizado.');
      setAdminPassword('');
    } catch (error) {
      setResult(error instanceof Error ? error.message : 'Error.');
    }
  }

  async function resetPassword() {
    if (!window.confirm(`Vas a reiniciar la contrasena de ${user.email} e invalidar sesiones previas. ¿Continuar?`)) return;
    try {
      const response = await resetUserPassword(projectId, user.id, adminPassword, temporary);
      setResult(response.temporary_password ? `Contrasena temporal (se muestra una vez): ${response.temporary_password}` : response.message);
      setTemporary('');
      setAdminPassword('');
      onUpdated({ ...user, must_change_password: true });
    } catch (error) {
      setResult(error instanceof Error ? error.message : 'Error.');
    }
  }

  async function resetMfa() {
    if (!window.confirm(`Vas a reiniciar MFA para ${user.email}. El usuario debera configurarlo nuevamente. ¿Continuar?`)) return;
    try {
      setResult(await resetUserMfa(projectId, user.id, adminPassword));
      setAdminPassword('');
      onUpdated({ ...user, mfa_enabled: false });
    } catch (error) {
      setResult(error instanceof Error ? error.message : 'Error.');
    }
  }

  async function generateQr() {
    try {
      setQrImageUrl(await generateEnrollmentQr(projectId, user.id));
    } catch (error) {
      setResult(error instanceof Error ? error.message : 'Error.');
    }
  }

  return (
    <section className="admin-user-card">
      <h3>{user.full_name}</h3>
      <small>{user.must_change_password ? 'Debe cambiar contrasena' : user.status} · MFA {user.mfa_enabled ? 'activo' : 'inactivo'}</small>
      <label>
        Correo
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      </label>
      <label>
        Contrasena temporal opcional
        <input type="password" minLength={15} maxLength={72} placeholder="Vacio = generar automaticamente" value={temporary} onChange={(event) => setTemporary(event.target.value)} />
      </label>
      <label>
        Tu contrasena administrativa
        <input type="password" maxLength={72} value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} />
      </label>
      <div>
        <button onClick={() => void changeEmail()}>Corregir correo</button>
        <button onClick={() => void resetPassword()}>Reiniciar contrasena</button>
        {user.mfa_enabled ? <button onClick={() => void resetMfa()}>Reiniciar MFA</button> : null}
        <button className="secondary" onClick={() => void generateQr()}>Generar QR de enrolamiento</button>
      </div>
      {qrImageUrl ? (
        <div className="enrollment-qr-preview">
          <img src={qrImageUrl} alt={`Codigo QR de enrolamiento para ${user.full_name}`} width={180} height={180} />
          <small>Valido por 15 minutos. Escanealo desde la app movil en /enroll.</small>
        </div>
      ) : null}
      {result ? <p role="status">{result}</p> : null}
    </section>
  );
}
