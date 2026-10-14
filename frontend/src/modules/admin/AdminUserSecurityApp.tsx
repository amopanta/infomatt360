import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { fetchAdminUsers, generateEnrollmentQr, resetUserMfa, resetUserPassword, updateUserEmail } from './api';
import type { AdminUser } from './api';

export function AdminUserSecurityApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [message, setMessage] = useState(t('admin.users.loading'));

  useEffect(() => {
    fetchAdminUsers(projectId)
      .then((rows) => {
        setUsers(rows);
        setMessage('');
      })
      .catch((error: Error) => setMessage(error.message));
  }, [projectId]);

  return (
    <AppShell title={t('admin.users.title')}>
      <main className="admin-users">
        <h2>{t('admin.users.projectUsers')}</h2>
        <p>{t('admin.users.sensitiveOpsWarning')}</p>
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
  const { t } = useI18n();
  const [email, setEmail] = useState(user.email);
  const [adminPassword, setAdminPassword] = useState('');
  const [temporary, setTemporary] = useState('');
  const [result, setResult] = useState('');
  const [qrImageUrl, setQrImageUrl] = useState('');

  async function changeEmail() {
    if (!window.confirm(t('admin.users.confirmChangeEmail', { from: user.email, to: email }))) return;
    try {
      const next = await updateUserEmail(projectId, user.id, email, adminPassword);
      onUpdated(next);
      setResult(t('admin.users.emailUpdated'));
      setAdminPassword('');
    } catch (error) {
      setResult(error instanceof Error ? error.message : t('admin.users.genericError'));
    }
  }

  async function resetPassword() {
    if (!window.confirm(t('admin.users.confirmResetPassword', { email: user.email }))) return;
    try {
      const response = await resetUserPassword(projectId, user.id, adminPassword, temporary);
      setResult(response.temporary_password ? t('admin.users.temporaryPasswordShown', { password: response.temporary_password }) : response.message);
      setTemporary('');
      setAdminPassword('');
      onUpdated({ ...user, must_change_password: true });
    } catch (error) {
      setResult(error instanceof Error ? error.message : t('admin.users.genericError'));
    }
  }

  async function resetMfa() {
    if (!window.confirm(t('admin.users.confirmResetMfa', { email: user.email }))) return;
    try {
      setResult(await resetUserMfa(projectId, user.id, adminPassword));
      setAdminPassword('');
      onUpdated({ ...user, mfa_enabled: false });
    } catch (error) {
      setResult(error instanceof Error ? error.message : t('admin.users.genericError'));
    }
  }

  async function generateQr() {
    try {
      setQrImageUrl(await generateEnrollmentQr(projectId, user.id));
    } catch (error) {
      setResult(error instanceof Error ? error.message : t('admin.users.genericError'));
    }
  }

  return (
    <section className="admin-user-card">
      <h3>{user.full_name}</h3>
      <small>{user.must_change_password ? t('admin.users.mustChangePassword') : user.status} · MFA {user.mfa_enabled ? t('admin.users.mfaActive') : t('admin.users.mfaInactive')}</small>
      <label>
        {t('admin.users.emailLabel')}
        <input type="email" value={email} onChange={(event) => setEmail(event.target.value)} />
      </label>
      <label>
        {t('admin.users.temporaryPasswordLabel')}
        <input type="password" minLength={15} maxLength={72} placeholder={t('admin.users.temporaryPasswordPlaceholder')} value={temporary} onChange={(event) => setTemporary(event.target.value)} />
      </label>
      <label>
        {t('admin.users.adminPasswordLabel')}
        <input type="password" maxLength={72} value={adminPassword} onChange={(event) => setAdminPassword(event.target.value)} />
      </label>
      <div>
        <button onClick={() => void changeEmail()}>{t('admin.users.correctEmail')}</button>
        <button onClick={() => void resetPassword()}>{t('admin.users.resetPassword')}</button>
        {user.mfa_enabled ? <button onClick={() => void resetMfa()}>{t('admin.users.resetMfa')}</button> : null}
        <button className="secondary" onClick={() => void generateQr()}>{t('admin.users.generateEnrollmentQr')}</button>
      </div>
      {qrImageUrl ? (
        <div className="enrollment-qr-preview">
          <img src={qrImageUrl} alt={t('admin.users.enrollmentQrAlt', { name: user.full_name })} width={180} height={180} />
          <small>{t('admin.users.qrValidityNote')}</small>
        </div>
      ) : null}
      {result ? <p role="status">{result}</p> : null}
    </section>
  );
}
