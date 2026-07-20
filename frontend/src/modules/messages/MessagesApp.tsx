import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchCounts, fetchExternalInbox, fetchInbox, fetchProjectUsers, fetchSent, markExternalRead, markMessageRead, sendMessage } from './api';
import type { ExternalMailMessage, InternalMessage, MessageCounts, MessageUser } from './api';

export function MessagesApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [inbox, setInbox] = useState<InternalMessage[]>([]);
  const [sent, setSent] = useState<InternalMessage[]>([]);
  const [external, setExternal] = useState<ExternalMailMessage[]>([]);
  const [counts, setCounts] = useState<MessageCounts>({ unread: 0, inbox: 0, sent: 0 });
  const [users, setUsers] = useState<MessageUser[]>([]);
  const [tab, setTab] = useState<'inbox' | 'sent' | 'external'>('inbox');
  const [message, setMessage] = useState('Cargando mensajes...');
  const [externalMessage, setExternalMessage] = useState('');

  async function reload() {
    const [nextInbox, nextSent, nextCounts] = await Promise.all([fetchInbox(projectId), fetchSent(projectId), fetchCounts(projectId)]);
    setInbox(nextInbox);
    setSent(nextSent);
    setCounts(nextCounts);
    setMessage(nextInbox.length || nextSent.length ? '' : 'No hay mensajes internos todavía.');
  }

  async function reloadExternal() {
    try {
      const nextExternal = await fetchExternalInbox(projectId);
      setExternal(nextExternal);
      setExternalMessage(nextExternal.length ? '' : 'No hay mensajes en la bandeja externa todavía.');
    } catch (error) {
      setExternalMessage(error instanceof Error ? error.message : 'No fue posible cargar la bandeja externa.');
    }
  }

  useEffect(() => {
    void reload().catch((error: Error) => setMessage(error.message));
    void reloadExternal();
    void fetchProjectUsers(projectId).then(setUsers).catch(() => setUsers([]));
  }, [projectId]);

  async function markRead(id: string) {
    try {
      await markMessageRead(projectId, id);
      await reload();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el mensaje.');
    }
  }

  async function markExternalReadHandler(id: string) {
    try {
      await markExternalRead(projectId, id);
      await reloadExternal();
    } catch (error) {
      setExternalMessage(error instanceof Error ? error.message : 'No fue posible actualizar el mensaje.');
    }
  }

  return (
    <AppShell title="Mensajes">
      <main className="messages-shell">
        <section className="messages-cards">
          <MessageCard label="No leídos" value={counts.unread} />
          <MessageCard label="Recibidos" value={counts.inbox} />
          <MessageCard label="Enviados" value={counts.sent} />
        </section>
        <ComposeMessage projectId={projectId} users={users} onSent={reload} onMessage={setMessage} />
        <section className="messages-panel">
          <header>
            <div>
              <h2>{tab === 'external' ? 'Bandeja externa' : 'Bandeja interna'}</h2>
              <p>{tab === 'external' ? 'Correos leídos por IMAP desde un buzón externo configurado en Correo autoconfigurado (solo lectura, ver docs/116).' : 'Comunicación operativa entre usuarios asignados al proyecto.'}</p>
            </div>
            <div className="messages-tabs">
              <button className={tab === 'inbox' ? 'active' : ''} onClick={() => setTab('inbox')}>Recibidos</button>
              <button className={tab === 'sent' ? 'active' : ''} onClick={() => setTab('sent')}>Enviados</button>
              <button className={tab === 'external' ? 'active' : ''} onClick={() => setTab('external')}>Bandeja externa</button>
            </div>
          </header>
          {tab === 'external' ? (
            <>
              {externalMessage ? <p role="status">{externalMessage}</p> : null}
              <ExternalMessageList messages={external} onRead={markExternalReadHandler} />
            </>
          ) : (
            <>
              {message ? <p role="status">{message}</p> : null}
              <MessageList messages={tab === 'inbox' ? inbox : sent} mode={tab} onRead={markRead} />
            </>
          )}
        </section>
      </main>
    </AppShell>
  );
}

function MessageCard({ label, value }: { label: string; value: number }) {
  return <article className="messages-card"><span>{label}</span><strong>{value.toLocaleString()}</strong></article>;
}

function ComposeMessage({ projectId, users, onSent, onMessage }: { projectId: string; users: MessageUser[]; onSent: () => Promise<void>; onMessage: (value: string) => void }) {
  const [recipientId, setRecipientId] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const activeUsers = useMemo(() => users.filter((user) => user.status === 'active'), [users]);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      await sendMessage(projectId, recipientId, subject, body);
      setSubject('');
      setBody('');
      onMessage('Mensaje enviado.');
      await onSent();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : 'No fue posible enviar el mensaje.');
    }
  }

  return (
    <form className="messages-compose" onSubmit={(event) => void submit(event)}>
      <h2>Nuevo mensaje</h2>
      <label>Destinatario
        <select required value={recipientId} onChange={(event) => setRecipientId(event.target.value)}>
          <option value="">Seleccionar usuario</option>
          {activeUsers.map((user) => <option key={user.id} value={user.id}>{user.full_name} · {user.email}</option>)}
        </select>
      </label>
      <label>Asunto<input required maxLength={250} value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
      <label>Mensaje<textarea required rows={4} value={body} onChange={(event) => setBody(event.target.value)} /></label>
      <button type="submit">Enviar</button>
    </form>
  );
}

function MessageList({ messages, mode, onRead }: { messages: InternalMessage[]; mode: 'inbox' | 'sent'; onRead: (id: string) => Promise<void> }) {
  if (!messages.length) return <p>No hay mensajes en esta bandeja.</p>;
  return (
    <div className="messages-list">
      {messages.map((item) => (
        <article key={item.id} className={`message-item ${item.status === 'unread' ? 'unread' : ''}`}>
          <header>
            <div>
              <strong>{item.subject}</strong>
              <small>{item.created_at ? new Date(item.created_at).toLocaleString() : 'Sin fecha'}</small>
            </div>
            <span>{item.status}</span>
          </header>
          <p>{item.body}</p>
          <small>{mode === 'inbox' ? `De: ${item.sender_id || 'Sistema'}` : `Para: ${item.recipient_id}`}</small>
          {mode === 'inbox' && item.status === 'unread' ? <button onClick={() => void onRead(item.id)}>Marcar leído</button> : null}
        </article>
      ))}
    </div>
  );
}

function ExternalMessageList({ messages, onRead }: { messages: ExternalMailMessage[]; onRead: (id: string) => Promise<void> }) {
  if (!messages.length) return <p>No hay mensajes en esta bandeja.</p>;
  return (
    <div className="messages-list">
      {messages.map((item) => (
        <article key={item.id} className={`message-item ${item.status === 'unread' ? 'unread' : ''}`}>
          <header>
            <div>
              <strong>{item.subject}</strong>
              <small>{item.received_at ? new Date(item.received_at).toLocaleString() : 'Sin fecha'}</small>
            </div>
            <span>{item.status}</span>
          </header>
          <p>{item.body}</p>
          <small>{`De: ${item.from_address}`}</small>
          {item.status === 'unread' ? <button onClick={() => void onRead(item.id)}>Marcar leído</button> : null}
        </article>
      ))}
    </div>
  );
}
