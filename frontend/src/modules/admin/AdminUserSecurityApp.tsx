import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { permissionLabel } from '../../lib/permissionLabels';
import { operationalStatusLabel } from '../../lib/operationalFormat';
import { createAdminRole, createAdminUser, fetchAdminRoles, fetchAdminUsers, fetchGrantablePermissions, generateEnrollmentQr, resetUserMfa, resetUserPassword, updateAdminAccess, updateUserEmail } from './api';
import type { AdminRole, AdminUser } from './api';

export function AdminUserSecurityApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [message, setMessage] = useState('Cargando usuarios...');
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [grantable, setGrantable] = useState<string[]>([]);
  const [query, setQuery] = useState('');

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchAdminUsers(projectId), fetchAdminRoles(projectId), fetchGrantablePermissions(projectId)])
      .then(([rows, availableRoles, permissions]) => {
        if (cancelled) return;
        setUsers(rows);
        setRoles(availableRoles);
        setGrantable(permissions);
        setMessage('');
      })
      .catch((error: Error) => { if (!cancelled) setMessage(error.message); });
    return () => { cancelled = true; };
  }, [projectId]);

  return (
    <AppShell title="Usuarios y permisos">
      <main className="admin-users">
        <h2>Usuarios del proyecto</h2>
        <p>Administra el acceso a este proyecto. Los cambios requieren tu contraseña administrativa y quedan auditados.</p>
        <UserProvisioning projectId={projectId} roles={roles} grantable={grantable} onCreated={(user) => setUsers((rows) => [...rows, user])} onRoleCreated={(role) => setRoles((rows) => [...rows, role])} />
        <label>Buscar usuario<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre, correo o rol" /></label>
        {message ? <p role="status">{message}</p> : null}
        {users.filter((user) => [user.full_name, user.email, user.role_name].some((value) => value?.toLocaleLowerCase().includes(query.trim().toLocaleLowerCase()))).map((user) => (
          <AdminUserCard
            key={user.id}
            projectId={projectId}
            user={user}
            roles={roles}
            onUpdated={() => { fetchAdminUsers(projectId).then(setUsers).catch((error: Error) => setMessage(error.message)); }}
          />
        ))}
      </main>
    </AppShell>
  );
}

function UserProvisioning({ projectId, roles, grantable, onCreated, onRoleCreated }: { projectId: string; roles: AdminRole[]; grantable: string[]; onCreated: (user: AdminUser) => void; onRoleCreated: (role: AdminRole) => void }) {
  const [draft, setDraft] = useState({ full_name: '', document_id: '', email: '', role_id: '' });
  const [password, setPassword] = useState('');
  const [roleName, setRoleName] = useState('');
  const [permissions, setPermissions] = useState<string[]>([]);
  const [temporary, setTemporary] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  async function provision(kind: 'user' | 'role') {
    if (busy || !window.confirm(kind === 'user' ? '¿Crear esta cuenta y concederle el rol seleccionado en este proyecto?' : '¿Crear el rol con los permisos seleccionados?')) return;
    setBusy(true); setMessage(''); setTemporary('');
    try {
      if (kind === 'user') {
        const result = await createAdminUser(projectId, draft, password);
        onCreated(result.user); setTemporary(result.temporary_password);
        setDraft({ full_name: '', document_id: '', email: '', role_id: '' });
        setMessage('Usuario creado. Deberá cambiar la contraseña al ingresar.');
      } else {
        onRoleCreated(await createAdminRole(projectId, roleName.trim(), permissions, password));
        setRoleName(''); setPermissions([]); setMessage('Rol creado.');
      }
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible completar la operación.'); }
    finally { setBusy(false); setPassword(''); }
  }
  return <section className="admin-user-card">
    <h3>Crear usuario</h3>
    <label>Nombre completo<input value={draft.full_name} onChange={(event) => setDraft({ ...draft, full_name: event.target.value })} /></label>
    <label>Documento<input value={draft.document_id} onChange={(event) => setDraft({ ...draft, document_id: event.target.value })} /></label>
    <label>Correo del nuevo usuario<input type="email" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} /></label>
    <label>Rol del nuevo usuario<select value={draft.role_id} onChange={(event) => setDraft({ ...draft, role_id: event.target.value })}><option value="">Seleccionar rol</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
    <details><summary>Crear un rol y seleccionar permisos</summary><label>Nombre del rol<input value={roleName} onChange={(event) => setRoleName(event.target.value)} /></label>{grantable.map((permission) => <label className="admin-permission-choice" key={permission}><input type="checkbox" checked={permissions.includes(permission)} onChange={(event) => setPermissions((current) => event.target.checked ? [...current, permission] : current.filter((item) => item !== permission))} />{permissionLabel(permission)}</label>)}<button disabled={busy || !password || roleName.trim().length < 3 || !permissions.length} onClick={() => void provision('role')}>Crear rol</button></details>
    <label>Contraseña administrativa para crear<input type="password" autoComplete="current-password" maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
    <button disabled={busy || !password || draft.full_name.trim().length < 3 || draft.document_id.trim().length < 5 || !draft.email || !draft.role_id} onClick={() => void provision('user')}>{busy ? 'Procesando…' : 'Crear usuario'}</button>
    {message && <p role="status">{message}</p>}
    {temporary && <div role="status"><p>Contraseña temporal: <code>{temporary}</code></p><button onClick={() => setTemporary('')}>Ocultar contraseña</button></div>}
  </section>;
}

function AdminUserCard({ projectId, user, roles, onUpdated }: { projectId: string; user: AdminUser; roles: AdminRole[]; onUpdated: (user: AdminUser) => void }) {
  const [email, setEmail] = useState(user.email);
  const [adminPassword, setAdminPassword] = useState('');
  const [temporary, setTemporary] = useState('');
  const [result, setResult] = useState('');
  const [qrImageUrl, setQrImageUrl] = useState('');
  const [roleId, setRoleId] = useState(user.role_id ?? '');
  const [assignmentStatus, setAssignmentStatus] = useState(user.assignment_status ?? 'active');
  useEffect(() => { setRoleId(user.role_id ?? ''); setAssignmentStatus(user.assignment_status ?? 'active'); }, [user.role_id, user.assignment_status]);
  const [accessBusy, setAccessBusy] = useState(false);

  async function changeAccess() {
    if (accessBusy || !window.confirm(`¿Actualizar el rol y acceso de ${user.full_name} en este proyecto?`)) return;
    setAccessBusy(true);
    try { onUpdated(await updateAdminAccess(projectId, user.id, roleId, assignmentStatus, adminPassword)); setResult('Acceso actualizado.'); }
    catch (error) { setResult(error instanceof Error ? error.message : 'Error al actualizar acceso.'); }
    finally { setAccessBusy(false); setAdminPassword(''); }
  }

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
      <small>Cuenta: {operationalStatusLabel(user.status)} · Acceso al proyecto: {operationalStatusLabel(user.assignment_status)} · MFA {user.mfa_enabled ? 'activo' : 'inactivo'}{user.must_change_password ? ' · Debe cambiar contraseña' : ''}</small>
      <label>Rol de {user.full_name}<select value={roleId} onChange={(event) => setRoleId(event.target.value)}><option value="">Sin rol</option>{user.role_id && !roles.some((role) => role.id === user.role_id) && <option value={user.role_id}>{user.role_name ?? 'Rol actual (no asignable)'}</option>}{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
      <label>Acceso de {user.full_name}<select value={assignmentStatus} onChange={(event) => setAssignmentStatus(event.target.value)}><option value="active">Activo</option><option value="suspended">Suspendido en este proyecto</option></select></label>
      <details><summary>Permisos efectivos ({user.permissions?.length ?? 0})</summary><ul>{user.permissions?.map((permission) => <li key={permission}>{permissionLabel(permission)}</li>)}</ul>{!!user.inherited_permissions?.length && <p>Incluye permisos heredados de la organización. Suspender el proyecto no elimina ese acceso.</p>}</details>
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
        <button disabled={accessBusy || !adminPassword || !roles.some((role) => role.id === roleId)} onClick={() => void changeAccess()}>{accessBusy ? 'Guardando…' : 'Guardar rol y acceso'}</button>
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
