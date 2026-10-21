import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
import { PROJECT_KEY } from '../auth/session';
import { permissionLabel } from '../../lib/permissionLabels';
import { operationalStatusLabel } from '../../lib/operationalFormat';
import { createAdminRole, createAdminUser, updateAdminProfile, fetchAdminRoles, fetchAdminUsers, fetchGrantablePermissions, generateEnrollmentQr, resetUserMfa, resetUserPassword, updateAdminAccess, updateUserEmail } from './api';
import type { AdminRole, AdminUser, NewProjectUser } from './api';

export function AdminUserSecurityApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [message, setMessage] = useState(t('admin.users.loading'));
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [grantable, setGrantable] = useState<string[]>([]);
  const [query, setQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [roleFilter, setRoleFilter] = useState('');
  const [selectedId, setSelectedId] = useState('');
  // Grilla de usuarios del proyecto (docs/145): búsqueda por nombre, documento,
  // cargo, municipio, correo o rol; los más recientes primero.
  const normalized = (value: string | null | undefined) => (value ?? '').normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLocaleLowerCase();
  const visibleUsers = users
    .filter((user) => !statusFilter || (statusFilter === 'incomplete' ? !user.position || !user.municipality : user.assignment_status === statusFilter))
    .filter((user) => !roleFilter || user.role_id === roleFilter)
    .filter((user) => !query.trim() || [user.full_name, user.document_id, user.position, user.municipality, user.department, user.email, user.role_name]
      .some((value) => normalized(value).includes(normalized(query.trim()))))
    .sort((a, b) => (b.created_at ?? '').localeCompare(a.created_at ?? ''));
  const selectedUser = users.find((user) => user.id === selectedId);

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
    <AppShell title={t('admin.users.title')}>
      <main className="admin-users">
        <h2>{t('admin.users.projectUsers')}</h2>
        <p>{t('admin.users.sensitiveOpsWarning')}</p>
        <p className="admin-users-bulk"><a className="button-link" href="/admin/excel-import?tipo=users">Crear varios usuarios por Excel</a> <small>(también en Avanzado → Carga masiva Excel → tipo «Usuarios»)</small></p>
        <UserProvisioning projectId={projectId} roles={roles} grantable={grantable} onCreated={(user) => { setUsers((rows) => [user, ...rows]); setSelectedId(user.id); }} onRoleCreated={(role) => setRoles((rows) => [...rows, role])} />
        <section className="admin-users-grid" aria-label="Usuarios creados en el proyecto">
          <h3>Usuarios creados ({visibleUsers.length} de {users.length})</h3>
          <div className="admin-users-filters">
            <label>Buscar usuario<input type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nombre, documento, cargo, municipio, correo o rol" /></label>
            <label>Acceso<select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">Todos</option><option value="active">Activos</option><option value="suspended">Suspendidos</option><option value="incomplete">Con datos incompletos</option></select></label>
            <label>Rol<select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value)}><option value="">Todos</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
          </div>
          <div className="records-table-wrap"><table className="records-table"><thead><tr><th>Nombre</th><th>Documento</th><th>Cargo</th><th>Municipio</th><th>Correo</th><th>Rol</th><th>Acceso</th><th>Creado</th><th /></tr></thead>
            <tbody>{visibleUsers.map((user) => <tr key={user.id} className={user.id === selectedId ? 'is-selected' : ''}>
              <td>{user.full_name}</td><td>{user.document_id || '—'}</td><td>{user.position || <em>Falta</em>}</td>
              <td>{user.municipality ? `${user.municipality}${user.department ? `, ${user.department}` : ''}` : <em>Falta</em>}</td>
              <td>{user.email}</td><td>{user.role_name || '—'}</td><td>{operationalStatusLabel(user.assignment_status)}</td>
              <td>{user.created_at ? new Date(user.created_at.endsWith('Z') ? user.created_at : `${user.created_at}Z`).toLocaleDateString() : '—'}</td>
              <td><button type="button" className="secondary" onClick={() => setSelectedId(user.id === selectedId ? '' : user.id)}>{user.id === selectedId ? 'Cerrar' : 'Gestionar'}</button></td></tr>)}
              {!visibleUsers.length && <tr><td colSpan={9}>No hay usuarios con esos filtros.</td></tr>}</tbody></table></div>
        </section>
        {message ? <p role="status">{message}</p> : null}
        {(selectedUser ? [selectedUser] : []).map((user) => (
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
  const [draft, setDraft] = useState<NewProjectUser>({ full_name: '', document_id: '', email: '', role_id: '', position: '', department: '', municipality: '', restrict_to_territory: true });
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
        setDraft({ full_name: '', document_id: '', email: '', role_id: '', position: '', department: '', municipality: '', restrict_to_territory: true });
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
    <label>Número de documento<input value={draft.document_id} onChange={(event) => setDraft({ ...draft, document_id: event.target.value })} /></label>
    <label>Cargo<input value={draft.position} placeholder="Ej. Gestor de campo" onChange={(event) => setDraft({ ...draft, position: event.target.value })} /></label>
    <label>Departamento<input value={draft.department} onChange={(event) => setDraft({ ...draft, department: event.target.value })} /></label>
    <label>Municipio<input value={draft.municipality} onChange={(event) => setDraft({ ...draft, municipality: event.target.value })} /></label>
    <label className="admin-permission-choice"><input type="checkbox" checked={draft.restrict_to_territory} onChange={(event) => setDraft({ ...draft, restrict_to_territory: event.target.checked })} />Limitar su acceso a este municipio (gestores y personal de campo)</label>
    <label>Correo del nuevo usuario<input type="email" value={draft.email} onChange={(event) => setDraft({ ...draft, email: event.target.value })} /></label>
    <label>Rol del nuevo usuario<select value={draft.role_id} onChange={(event) => setDraft({ ...draft, role_id: event.target.value })}><option value="">Seleccionar rol</option>{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
    <details><summary>Crear un rol y seleccionar permisos</summary><label>Nombre del rol<input value={roleName} onChange={(event) => setRoleName(event.target.value)} /></label>{grantable.map((permission) => <label className="admin-permission-choice" key={permission}><input type="checkbox" checked={permissions.includes(permission)} onChange={(event) => setPermissions((current) => event.target.checked ? [...current, permission] : current.filter((item) => item !== permission))} />{permissionLabel(permission)}</label>)}<button disabled={busy || !password || roleName.trim().length < 3 || !permissions.length} onClick={() => void provision('role')}>Crear rol</button></details>
    <label>Contraseña administrativa para crear<input type="password" autoComplete="current-password" maxLength={72} value={password} onChange={(event) => setPassword(event.target.value)} /></label>
    <button disabled={busy || !password || draft.full_name.trim().length < 3 || draft.document_id.trim().length < 5 || draft.position.trim().length < 2 || draft.department.trim().length < 2 || draft.municipality.trim().length < 2 || !draft.email || !draft.role_id} onClick={() => void provision('user')}>{busy ? 'Procesando…' : 'Crear usuario'}</button>
    {message && <p role="status">{message}</p>}
    {temporary && <div role="status"><p>Contraseña temporal: <code>{temporary}</code></p><button onClick={() => setTemporary('')}>Ocultar contraseña</button></div>}
  </section>;
}

function AdminUserCard({ projectId, user, roles, onUpdated }: { projectId: string; user: AdminUser; roles: AdminRole[]; onUpdated: (user: AdminUser) => void }) {
  const { t } = useI18n();
  const [email, setEmail] = useState(user.email);
  const [adminPassword, setAdminPassword] = useState('');
  const [temporary, setTemporary] = useState('');
  const [result, setResult] = useState('');
  const [qrImageUrl, setQrImageUrl] = useState('');
  const [roleId, setRoleId] = useState(user.role_id ?? '');
  const [assignmentStatus, setAssignmentStatus] = useState(user.assignment_status ?? 'active');
  useEffect(() => { setRoleId(user.role_id ?? ''); setAssignmentStatus(user.assignment_status ?? 'active'); }, [user.role_id, user.assignment_status]);
  const [accessBusy, setAccessBusy] = useState(false);
  const [profile, setProfile] = useState({ full_name: user.full_name, position: user.position ?? '', department: user.department ?? '', municipality: user.municipality ?? '', phone: user.phone ?? '' });
  useEffect(() => { setProfile({ full_name: user.full_name, position: user.position ?? '', department: user.department ?? '', municipality: user.municipality ?? '', phone: user.phone ?? '' }); }, [user.full_name, user.position, user.department, user.municipality, user.phone]);

  async function changeProfile() {
    if (accessBusy || !window.confirm(`¿Actualizar los datos de ${user.full_name}? Los registros ya capturados conservan los datos que tenía al capturar.`)) return;
    setAccessBusy(true);
    try { onUpdated(await updateAdminProfile(projectId, user.id, profile, adminPassword)); setResult('Datos actualizados.'); }
    catch (error) { setResult(error instanceof Error ? error.message : 'Error al actualizar los datos.'); }
    finally { setAccessBusy(false); setAdminPassword(''); }
  }

  async function changeAccess() {
    if (accessBusy || !window.confirm(`¿Actualizar el rol y acceso de ${user.full_name} en este proyecto?`)) return;
    setAccessBusy(true);
    try { onUpdated(await updateAdminAccess(projectId, user.id, roleId, assignmentStatus, adminPassword)); setResult('Acceso actualizado.'); }
    catch (error) { setResult(error instanceof Error ? error.message : 'Error al actualizar acceso.'); }
    finally { setAccessBusy(false); setAdminPassword(''); }
  }

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
      <p className="admin-user-profile">Documento {user.document_id || '—'} · {user.position || 'Sin cargo'} · {[user.municipality, user.department].filter(Boolean).join(', ') || 'Sin municipio'}</p>
      {!user.position || !user.municipality ? <p role="alert">Faltan datos obligatorios (cargo y municipio): complétalos en «Datos de la persona».</p> : null}
      <details><summary>Datos de la persona</summary>
        <label>Nombre completo<input value={profile.full_name} onChange={(event) => setProfile({ ...profile, full_name: event.target.value })} /></label>
        <label>Cargo<input value={profile.position} onChange={(event) => setProfile({ ...profile, position: event.target.value })} /></label>
        <label>Departamento<input value={profile.department} onChange={(event) => setProfile({ ...profile, department: event.target.value })} /></label>
        <label>Municipio<input value={profile.municipality} onChange={(event) => setProfile({ ...profile, municipality: event.target.value })} /></label>
        <label>Teléfono<input value={profile.phone} onChange={(event) => setProfile({ ...profile, phone: event.target.value })} /></label>
        <button disabled={accessBusy || !adminPassword || profile.full_name.trim().length < 3 || profile.position.trim().length < 2 || profile.department.trim().length < 2 || profile.municipality.trim().length < 2} onClick={() => void changeProfile()}>Guardar datos (requiere tu contraseña administrativa, abajo)</button>
      </details>
      <small>Cuenta: {operationalStatusLabel(user.status)} · Acceso al proyecto: {operationalStatusLabel(user.assignment_status)} · MFA {user.mfa_enabled ? 'activo' : 'inactivo'}{user.must_change_password ? ' · Debe cambiar contraseña' : ''}</small>
      <label>Rol de {user.full_name}<select value={roleId} onChange={(event) => setRoleId(event.target.value)}><option value="">Sin rol</option>{user.role_id && !roles.some((role) => role.id === user.role_id) && <option value={user.role_id}>{user.role_name ?? 'Rol actual (no asignable)'}</option>}{roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>
      <label>Acceso de {user.full_name}<select value={assignmentStatus} onChange={(event) => setAssignmentStatus(event.target.value)}><option value="active">Activo</option><option value="suspended">Suspendido en este proyecto</option></select></label>
      <details><summary>Permisos efectivos ({user.permissions?.length ?? 0})</summary><ul>{user.permissions?.map((permission) => <li key={permission}>{permissionLabel(permission)}</li>)}</ul>{!!user.inherited_permissions?.length && <p>Incluye permisos heredados de la organización. Suspender el proyecto no elimina ese acceso.</p>}</details>
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
        <button disabled={accessBusy || !adminPassword || !roles.some((role) => role.id === roleId)} onClick={() => void changeAccess()}>{accessBusy ? 'Guardando…' : 'Guardar rol y acceso'}</button>
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
