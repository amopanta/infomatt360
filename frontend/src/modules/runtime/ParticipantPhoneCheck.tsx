import { useState } from 'react';
import type { EligibleParticipant } from './api';
import { updateAssignedParticipantPhone } from './api';
import { participantPhone } from './ParticipantSummaryTable';

export function ParticipantPhoneCheck({ person, templateId, assignmentReady, onUpdated }: {
  person: EligibleParticipant;
  templateId: string;
  assignmentReady: boolean;
  onUpdated: (person: EligibleParticipant) => void;
}) {
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
      setMessage('Teléfono actualizado en la ficha del participante.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible actualizar el teléfono.');
    } finally {
      setSaving(false);
    }
  }

  return <div className="runtime-phone-check">
    <fieldset disabled={!assignmentReady || saving}>
      <legend>¿El teléfono del participante está actualizado?</legend>
      <p>Teléfono registrado: <strong>{currentPhone || 'No registrado'}</strong></p>
      <div className="runtime-phone-options">
        <label><input type="radio" name={`phone-current-${person.id}`} checked={answer === 'yes'} disabled={!currentPhone}
          onChange={() => { setAnswer('yes'); setMessage(''); }} /> Sí, es correcto</label>
        <label><input type="radio" name={`phone-current-${person.id}`} checked={answer === 'no'}
          onChange={() => { setAnswer('no'); setMessage(''); }} /> No, registrar uno nuevo</label>
      </div>
      {answer === 'no' && <div className="runtime-phone-update">
        <label>Teléfono actualizado<input type="tel" autoComplete="tel" value={newPhone} maxLength={25}
          onChange={(event) => setNewPhone(event.target.value)} placeholder="Ej. 3001234567" /></label>
        <button type="button" disabled={!/^\+?[0-9 ()-]{7,25}$/.test(newPhone.trim())} onClick={() => void savePhone()}>
          {saving ? 'Guardando...' : 'Guardar teléfono'}
        </button>
      </div>}
    </fieldset>
    {message && <p role="status">{message}</p>}
  </div>;
}
