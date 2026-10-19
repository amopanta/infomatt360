/**
 * Panel "Validación y retroalimentación" (docs/141 §6).
 *
 * - Revisor: devuelve con observaciones por pregunta o integrante de un
 *   REPEAT, al autor o a otro gestor; luego verifica o rechaza cada corrección.
 * - Destinatario: ve las observaciones, salta a la pregunta y las marca
 *   corregidas. Las observaciones nunca cambian las respuestas.
 */
import { useEffect, useMemo, useState } from 'react';
import { useI18n } from '../../i18n';
import { currentProjectPermissions } from '../auth/session';
import type { RuntimeRecord } from './api';
import {
  currentUserId, fetchObservations, fetchProjectUsers, observationTargets, returnWithObservations, updateObservation,
  type Observation, type ObservationStatus, type ProjectUser,
} from './feedbackApi';

const RETURNABLE = new Set(['submitted', 'under_review', 'tech_approved', 'coordinator_approved']);
type Draft = { target: string; reason: string; requested_action: string };
const emptyDraft = (): Draft => ({ target: '', reason: '', requested_action: '' });

export function ObservationsPanel({ projectId, record, onChanged, onMessage }: {
  projectId: string; record: RuntimeRecord; onChanged: () => void; onMessage: (value: string) => void;
}) {
  const { t } = useI18n();
  const permissions = currentProjectPermissions();
  const isReviewer = permissions.has('records.review') || permissions.has('records.approve');
  const me = currentUserId();
  const isRecipient = Boolean(me && record.correction_user_id === me);
  const [observations, setObservations] = useState<Observation[]>([]);
  const [users, setUsers] = useState<ProjectUser[]>([]);
  const [notes, setNotes] = useState('');
  const [assignee, setAssignee] = useState('');
  const [drafts, setDrafts] = useState<Draft[]>([emptyDraft()]);
  const [busy, setBusy] = useState(false);
  const targets = useMemo(() => observationTargets(record.values), [record.values]);
  const userName = (id: string | null | undefined) => users.find((u) => u.id === id)?.full_name ?? id ?? '';

  async function reload() {
    setObservations(await fetchObservations(record.id).catch(() => []));
  }
  useEffect(() => { void reload(); }, [record.id, record.status]);
  useEffect(() => { if (isReviewer) void fetchProjectUsers(projectId).then(setUsers).catch(() => setUsers([])); }, [projectId, isReviewer]);

  async function submitReturn() {
    const items = drafts.filter((d) => d.reason.trim());
    setBusy(true);
    try {
      await returnWithObservations(record.id, {
        notes: notes.trim(),
        assignee_user_id: assignee || null,
        observations: items.map((d) => {
          const target = targets.find((x) => x.value === d.target);
          return { field_name: target?.field, repeat_path: target?.path, reason: d.reason.trim(), requested_action: d.requested_action.trim() || undefined };
        }),
      });
      setNotes(''); setAssignee(''); setDrafts([emptyDraft()]);
      onMessage(t('feedback.returned'));
      onChanged();
      await reload();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : t('feedback.error'));
    } finally {
      setBusy(false);
    }
  }

  async function setStatus(item: Observation, status: ObservationStatus) {
    try {
      await updateObservation(item.id, status);
      await reload();
    } catch (error) {
      onMessage(error instanceof Error ? error.message : t('feedback.error'));
    }
  }

  function goTo(item: Observation) {
    const key = item.field_name ? `field-${(item.repeat_path ?? item.field_name).split('[')[0]}` : '';
    document.getElementById(key)?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  }

  const canReturn = isReviewer && RETURNABLE.has(record.status);
  if (!canReturn && observations.length === 0) return null;

  return (
    <section className="review-panel feedback-panel">
      <h3>{t('feedback.title')}</h3>
      {record.status === 'returned' || record.status === 'corrected' ? (
        <p className="feedback-recipient">{isRecipient ? t('feedback.youMustCorrect') : t('feedback.recipient', { name: userName(record.correction_user_id) })}</p>
      ) : null}

      {observations.length > 0 && (
        <ol className="feedback-list">
          {observations.map((item) => (
            <li key={item.id} className={`feedback-item status-${item.status}`}>
              <div>
                <strong>{item.repeat_path || item.field_name || t('feedback.general')}</strong>
                <span className="feedback-status">{t(`feedback.status.${item.status}`)}</span>
              </div>
              <p>{item.reason}</p>
              {item.requested_action && <p><em>{t('feedback.requested')}: {item.requested_action}</em></p>}
              {item.response_note && <p><small>{t('feedback.response')}: {item.response_note}</small></p>}
              <div className="review-actions">
                {item.field_name && <button type="button" onClick={() => goTo(item)}>{t('feedback.goTo')}</button>}
                {isRecipient && ['pending', 'in_correction', 'rejected'].includes(item.status) && <button type="button" onClick={() => void setStatus(item, 'corrected')}>{t('feedback.markCorrected')}</button>}
                {isReviewer && item.status === 'corrected' && <>
                  <button type="button" onClick={() => void setStatus(item, 'verified')}>{t('feedback.verify')}</button>
                  <button type="button" onClick={() => void setStatus(item, 'rejected')}>{t('feedback.reject')}</button>
                </>}
              </div>
            </li>
          ))}
        </ol>
      )}

      {canReturn && (
        <div className="feedback-form">
          <h4>{t('feedback.returnTitle')}</h4>
          <label>{t('feedback.generalReason')}<textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} /></label>
          <label>{t('feedback.whoCorrects')}
            <select value={assignee} onChange={(e) => setAssignee(e.target.value)}>
              <option value="">{t('feedback.originalAuthor')}</option>
              {users.filter((u) => u.id !== record.submitted_by).map((u) => <option key={u.id} value={u.id}>{u.full_name}</option>)}
            </select>
          </label>
          {drafts.map((draft, index) => (
            <div key={index} className="feedback-draft">
              <select aria-label={t('feedback.question')} value={draft.target} onChange={(e) => setDrafts((rows) => rows.map((r, i) => (i === index ? { ...r, target: e.target.value } : r)))}>
                <option value="">{t('feedback.general')}</option>
                {targets.map((x) => <option key={x.value} value={x.value}>{x.label}</option>)}
              </select>
              <input aria-label={t('feedback.reason')} placeholder={t('feedback.reason')} value={draft.reason} onChange={(e) => setDrafts((rows) => rows.map((r, i) => (i === index ? { ...r, reason: e.target.value } : r)))} />
              <input aria-label={t('feedback.requested')} placeholder={t('feedback.requested')} value={draft.requested_action} onChange={(e) => setDrafts((rows) => rows.map((r, i) => (i === index ? { ...r, requested_action: e.target.value } : r)))} />
              {drafts.length > 1 && <button type="button" onClick={() => setDrafts((rows) => rows.filter((_, i) => i !== index))}>✕</button>}
            </div>
          ))}
          <div className="review-actions">
            <button type="button" onClick={() => setDrafts((rows) => [...rows, emptyDraft()])}>{t('feedback.addObservation')}</button>
            <button type="button" disabled={busy || notes.trim().length < 3} onClick={() => void submitReturn()}>{t('feedback.returnButton')}</button>
          </div>
        </div>
      )}
    </section>
  );
}
