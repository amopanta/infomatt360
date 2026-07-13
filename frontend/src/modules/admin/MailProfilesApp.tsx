import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { createMailProfile, fetchMailProfiles, suggestMailAutoconfig, testSendMailProfile } from './mailApi';
import type { MailProfile } from './mailApi';

export function MailProfilesApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [profiles, setProfiles] = useState<MailProfile[]>([]);
  const [message, setMessage] = useState('');
  const [testMessages, setTestMessages] = useState<Record<string, string>>({});

  const [name, setName] = useState('');
  const [senderEmail, setSenderEmail] = useState('');
  const [serverHost, setServerHost] = useState('');
  const [serverPort, setServerPort] = useState('');
  const [useTls, setUseTls] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [autoconfigNote, setAutoconfigNote] = useState('');
  const [creating, setCreating] = useState(false);
  const [testingId, setTestingId] = useState<string | null>(null);

  async function loadProfiles() {
    if (!projectId) return;
    try {
      setProfiles(await fetchMailProfiles(projectId));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar los perfiles de correo.');
    }
  }

  useEffect(() => { void loadProfiles(); }, [projectId]);

  async function handleEmailBlur() {
    const email = senderEmail.trim();
    if (!email.includes('@')) return;
    try {
      const suggestion = await suggestMailAutoconfig(email);
      if (suggestion.found) {
        setServerHost(suggestion.server_host ?? '');
        setServerPort(suggestion.server_port ?? '');
        setUseTls(suggestion.use_tls ?? true);
        setAutoconfigNote(`Servidor sugerido automaticamente para ${email.split('@')[1]}.`);
      } else {
        setAutoconfigNote('Dominio no reconocido: completa el servidor SMTP manualmente.');
      }
    } catch {
      setAutoconfigNote('');
    }
  }

  async function submitCreate() {
    setCreating(true);
    try {
      await createMailProfile({
        projectId,
        name: name.trim() || senderEmail.trim(),
        senderEmail: senderEmail.trim(),
        serverHost: serverHost.trim(),
        serverPort: serverPort.trim(),
        useTls,
        username: username.trim(),
        password,
        isDefault,
      });
      setMessage('Perfil de correo creado. Usa "Enviar prueba" para validar el envio real.');
      setName('');
      setSenderEmail('');
      setServerHost('');
      setServerPort('');
      setUsername('');
      setPassword('');
      setIsDefault(false);
      setAutoconfigNote('');
      await loadProfiles();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear el perfil de correo.');
    } finally {
      setCreating(false);
    }
  }

  async function submitTestSend(profileId: string) {
    setTestingId(profileId);
    try {
      const result = await testSendMailProfile(profileId);
      setTestMessages((current) => ({ ...current, [profileId]: result.detail }));
    } catch (error) {
      setTestMessages((current) => ({ ...current, [profileId]: error instanceof Error ? error.message : 'No fue posible enviar el correo de prueba.' }));
    } finally {
      setTestingId(null);
    }
  }

  return (
    <AppShell title="Correo autoconfigurado">
      <main className="audit-shell">
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        <section className="audit-panel">
          <header>
            <div>
              <h2>Nuevo perfil de correo</h2>
              <p>Al escribir el correo remitente se sugiere el servidor SMTP para proveedores conocidos (Gmail, Outlook/Office365, Yahoo); ver docs/75.</p>
            </div>
          </header>
          <div className="ai-analyze-inline">
            <label>Nombre<input value={name} onChange={(event) => setName(event.target.value)} placeholder="Correo institucional" /></label>
            <label>Correo remitente<input value={senderEmail} onChange={(event) => setSenderEmail(event.target.value)} onBlur={() => void handleEmailBlur()} placeholder="notificaciones@midominio.com" /></label>
            <label>Servidor SMTP<input value={serverHost} onChange={(event) => setServerHost(event.target.value)} placeholder="smtp.midominio.com" /></label>
            <label>Puerto<input value={serverPort} onChange={(event) => setServerPort(event.target.value)} placeholder="587" /></label>
            <label>Usuario<input value={username} onChange={(event) => setUsername(event.target.value)} /></label>
            <label>Contraseña<input type="password" value={password} onChange={(event) => setPassword(event.target.value)} /></label>
            <label><input type="checkbox" checked={useTls} onChange={(event) => setUseTls(event.target.checked)} /> Usar TLS (STARTTLS)</label>
            <label><input type="checkbox" checked={isDefault} onChange={(event) => setIsDefault(event.target.checked)} /> Predeterminado</label>
            <button className="primary" disabled={creating || !senderEmail.trim() || !serverHost.trim() || !serverPort.trim()} onClick={() => void submitCreate()}>
              {creating ? 'Creando…' : 'Crear perfil'}
            </button>
          </div>
          {autoconfigNote ? <p>{autoconfigNote}</p> : null}
        </section>

        <section className="audit-panel">
          <header>
            <div>
              <h2>Perfiles del proyecto</h2>
              <p>Envia un correo de prueba real antes de dar por buena la configuracion.</p>
            </div>
          </header>
          {!profiles.length ? <p>Aun no hay perfiles de correo para este proyecto.</p> : null}
          <div className="audit-table-wrap">
            <table className="audit-table">
              <thead>
                <tr>
                  <th>Nombre</th>
                  <th>Remitente</th>
                  <th>Servidor</th>
                  <th>Predeterminado</th>
                  <th>Resultado de prueba</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {profiles.map((profile) => (
                  <tr key={profile.id}>
                    <td>{profile.name}</td>
                    <td>{profile.sender_email}</td>
                    <td>{profile.server_host ? `${profile.server_host}:${profile.server_port ?? ''}` : '—'}</td>
                    <td>{profile.is_default ? 'Si' : 'No'}</td>
                    <td>{testMessages[profile.id] ?? '—'}</td>
                    <td>
                      <button disabled={testingId === profile.id} onClick={() => void submitTestSend(profile.id)}>
                        {testingId === profile.id ? 'Enviando…' : 'Enviar prueba'}
                      </button>
                    </td>
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
