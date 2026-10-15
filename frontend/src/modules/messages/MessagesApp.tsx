import { useEffect, useMemo, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchCounts, fetchExternalInbox, fetchInbox, fetchProjectUsers, fetchSent, markExternalRead, markMessageRead, sendMessage } from './api';
import type { ExternalMailMessage, InternalMessage, MessageCounts, MessageUser } from './api';
import { useI18n } from '../../i18n';

export function MessagesApp() {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [inbox, setInbox] = useState<InternalMessage[]>([]);
  const [sent, setSent] = useState<InternalMessage[]>([]);
  const [external, setExternal] = useState<ExternalMailMessage[]>([]);
  const [counts, setCounts] = useState<MessageCounts>({ unread: 0, inbox: 0, sent: 0 });
  const [users, setUsers] = useState<MessageUser[]>([]);
  const [tab, setTab] = useState<'notifications' | 'inbox' | 'sent' | 'external'>('notifications');
  const [message, setMessage] = useState(t('messages.loadingMessages'));
  const [externalMessage, setExternalMessage] = useState('');

  async function reload() {
    const [nextInbox, nextSent, nextCounts] = await Promise.all([fetchInbox(projectId), fetchSent(projectId), fetchCounts(projectId)]);
    setInbox(nextInbox);
    setSent(nextSent);
    setCounts(nextCounts);
    setMessage(nextInbox.length || nextSent.length ? '' : t('messages.noInternalMessages'));
  }

  async function reloadExternal() {
    try {
      const nextExternal = await fetchExternalInbox(projectId);
      setExternal(nextExternal);
      setExternalMessage(nextExternal.length ? '' : t('messages.noExternalMessages'));
    } catch (error) {
      setExternalMessage(error instanceof Error ? error.message : t('messages.externalLoadFailed'));
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
      setMessage(error instanceof Error ? error.message : t('messages.messageUpdateFailed'));
    }
  }

  async function markExternalReadHandler(id: string) {
    try {
      await markExternalRead(projectId, id);
      await reloadExternal();
    } catch (error) {
      setExternalMessage(error instanceof Error ? error.message : t('messages.messageUpdateFailed'));
    }
  }

  return (
    <AppShell title={t('messages.internalInbox')}>
      <main className="messages-shell">
        <section className="messages-cards">
          <MessageCard label={t('messages.unread')} value={counts.unread} />
          <MessageCard label={t('messages.received')} value={counts.inbox} />
          <MessageCard label={t('messages.sentLabel')} value={counts.sent} />
        </section>
        <ComposeMessage projectId={projectId} users={users} onSent={reload} onMessage={setMessage} />
        <section className="messages-panel">
          <header>
            <div>
              <h2>{tab === 'external' ? t('messages.externalInbox') : t('messages.internalInbox')}</h2>
              <p>{tab === 'external' ? t('messages.externalDescription') : t('messages.internalDescription')}</p>
            </div>
            <div className="messages-tabs">
              <button className={tab === 'inbox' ? 'active' : ''} onClick={() => setTab('inbox')}>{t('messages.receivedTab')}</button>
              <button className={tab === 'notifications' ? 'active' : ''} onClick={() => setTab('notifications')}>{t('messages.reviewNotifications')}</button>
              <button className={tab === 'sent' ? 'active' : ''} onClick={() => setTab('sent')}>{t('messages.sentTab')}</button>
              <button className={tab === 'external' ? 'active' : ''} onClick={() => setTab('external')}>{t('messages.externalTab')}</button>
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
              <MessageList messages={tab === 'sent' ? sent : tab === 'notifications' ? inbox.filter((item) => item.subject.startsWith('Revisión de registro:') || item.subject.startsWith('Registro ')) : inbox} mode={tab === 'sent' ? 'sent' : 'inbox'} onRead={markRead} />
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
  const { t } = useI18n();
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
      onMessage(t('messages.messageSent'));
      await onSent();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : t('messages.sendFailed'));
    }
  }

  return (
    <form className="messages-compose" onSubmit={(event) => void submit(event)}>
      <h2>{t('messages.newMessage')}</h2>
      <label>{t('messages.recipient')}
        <select required value={recipientId} onChange={(event) => setRecipientId(event.target.value)}>
          <option value="">{t('messages.selectUser')}</option>
          {activeUsers.map((user) => <option key={user.id} value={user.id}>{user.full_name} · {user.email}</option>)}
        </select>
      </label>
      <label>{t('messages.subject')}<input required maxLength={250} value={subject} onChange={(event) => setSubject(event.target.value)} /></label>
      <label>{t('messages.messageBody')}<textarea required rows={4} value={body} onChange={(event) => setBody(event.target.value)} /></label>
      <button type="submit">{t('messages.send')}</button>
    </form>
  );
}

function MessageList({ messages, mode, onRead }: { messages: InternalMessage[]; mode: 'inbox' | 'sent'; onRead: (id: string) => Promise<void> }) {
  const { t } = useI18n();
  if (!messages.length) return <p>{t('messages.noMessagesInBox')}</p>;
  return (
    <div className="messages-list">
      {messages.map((item) => (
        <article key={item.id} className={`message-item ${item.status === 'unread' ? 'unread' : ''}`}>
          <header>
            <div>
              <strong>{item.subject}</strong>
              <small>{item.created_at ? new Date(item.created_at).toLocaleString() : t('messages.noDate')}</small>
            </div>
            <span>{item.status}</span>
          </header>
          <p>{item.body}</p>
          <small>{mode === 'inbox' ? t('messages.fromSender', { sender: item.sender_id || t('messages.fromSystem') }) : t('messages.toRecipient', { recipient: item.recipient_id })}</small>
          {mode === 'inbox' && item.status === 'unread' ? <button onClick={() => void onRead(item.id)}>{t('messages.markRead')}</button> : null}
        </article>
      ))}
    </div>
  );
}

function ExternalMessageList({ messages, onRead }: { messages: ExternalMailMessage[]; onRead: (id: string) => Promise<void> }) {
  const { t } = useI18n();
  if (!messages.length) return <p>{t('messages.noMessagesInBox')}</p>;
  return (
    <div className="messages-list">
      {messages.map((item) => (
        <article key={item.id} className={`message-item ${item.status === 'unread' ? 'unread' : ''}`}>
          <header>
            <div>
              <strong>{item.subject}</strong>
              <small>{item.received_at ? new Date(item.received_at).toLocaleString() : t('messages.noDate')}</small>
            </div>
            <span>{item.status}</span>
          </header>
          <p>{item.body}</p>
          <small>{t('messages.fromSender', { sender: item.from_address })}</small>
          {item.status === 'unread' ? <button onClick={() => void onRead(item.id)}>{t('messages.markRead')}</button> : null}
        </article>
      ))}
    </div>
  );
}
