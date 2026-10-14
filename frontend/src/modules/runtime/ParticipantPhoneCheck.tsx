import { useState } from 'react';
import type { EligibleParticipant } from './api';
import { updateAssignedParticipantPhone } from './api';
import { participantPhone } from './ParticipantSummaryTable';
import { useI18n } from '../../i18n';

export function ParticipantPhoneCheck({ person, templateId, assignmentReady, onUpdated }: {
  person: EligibleParticipant;
  templateId: string;
  assignmentReady: boolean;
  onUpdated: (person: EligibleParticipant) => void;
}) {
  const { t } = useI18n();
  const [answer, setAnswer] = useState<'yes' | 'no' | ''>('');
  const [newPhone, setNewPhone] = useState('');
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const currentPhone = participantPhone(person);

  async function savePhone() {
    setSaving(true);
    setMessage('');
    try {
      const updated = await updateAssignedParticipantPhone(templateId, person.id, newPhone.trim());
      onUpdated(updated);
      setNewPhone('');
      setAnswer('yes');
      setMessage(t('runtime.phoneUpdated'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('runtime.phoneUpdateFailed'));
    } finally {
      setSaving(false);
    }
  }

  return <div className="runtime-phone-check">
    <fieldset disabled={!assignmentReady || saving}>
      <legend>{t('runtime.phoneQuestion')}</legend>
      <p>{t('runtime.registeredPhone')} <strong>{currentPhone || t('runtime.notRegistered')}</strong></p>
      <div className="runtime-phone-options">
        <label><input type="radio" name={`phone-current-${person.id}`} checked={answer === 'yes'} disabled={!currentPhone}
          onChange={() => { setAnswer('yes'); setMessage(''); }} /> {t('runtime.phoneCorrect')}</label>
        <label><input type="radio" name={`phone-current-${person.id}`} checked={answer === 'no'}
          onChange={() => { setAnswer('no'); setMessage(''); }} /> {t('runtime.phoneRegisterNew')}</label>
      </div>
      {answer === 'no' && <div className="runtime-phone-update">
        <label>{t('runtime.updatedPhoneLabel')}<input type="tel" autoComplete="tel" value={newPhone} maxLength={25}
          onChange={(event) => setNewPhone(event.target.value)} placeholder={t('runtime.phonePlaceholder')} /></label>
        <button type="button" disabled={!/^\+?[0-9 ()-]{7,25}$/.test(newPhone.trim())} onClick={() => void savePhone()}>
          {saving ? t('runtime.savingPhone') : t('runtime.savePhone')}
        </button>
      </div>}
    </fieldset>
    {message && <p role="status">{message}</p>}
  </div>;
}
