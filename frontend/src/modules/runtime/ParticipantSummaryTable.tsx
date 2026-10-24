import type { EligibleParticipant } from './api';
import { useI18n } from '../../i18n';
import { operationalStatusLabel } from '../../lib/operationalFormat';

type ParticipantColumn = { label: string; value: string };

function metadataLabels(t: (key: string) => string): Record<string, string> {
  return {
    department: t('runtime.metaDepartment'), departamento: t('runtime.metaDepartment'),
    municipality: t('runtime.metaMunicipality'), municipio: t('runtime.metaMunicipality'),
    group_name: t('runtime.metaGroup'),
  };
}
const phoneKeys = ['phone', 'telefono', 'teléfono', 'celular', 'mobile', 'phone_number'];

export function participantPhone(person: EligibleParticipant): string {
  try {
    const metadata = JSON.parse(person.metadata_json || '{}');
    if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return '';
    const entry = Object.entries(metadata).find(([key, value]) => phoneKeys.includes(key.trim().toLocaleLowerCase()) && value !== null && value !== undefined && value !== '');
    return String(entry?.[1] ?? '');
  } catch { return ''; }
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.map(displayValue).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function metadataColumns(person: EligibleParticipant, t: (key: string) => string): ParticipantColumn[] {
  let metadata: unknown;
  try { metadata = JSON.parse(person.metadata_json || '{}'); } catch { return []; }
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return [];
  const labels = metadataLabels(t);
  const ignored = new Set(['department', 'departamento', 'municipality', 'municipio', 'group_name', ...phoneKeys]);
  return Object.entries(metadata).filter(([key]) => !ignored.has(key.trim().toLocaleLowerCase())).map(([key, value]) => ({
    label: labels[key] || key.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase()),
    value: displayValue(value),
  }));
}

export function ParticipantSummaryTable({ person, assignmentReady }: { person: EligibleParticipant; assignmentReady: boolean }) {
  const { t } = useI18n();
  const columns: ParticipantColumn[] = [
    { label: t('runtime.colFullName'), value: displayValue(person.full_name) },
    { label: t('runtime.colDocument'), value: displayValue(person.document_id) },
    { label: t('runtime.colCode'), value: displayValue(person.external_code) },
    { label: t('runtime.colPhone'), value: displayValue(participantPhone(person)) },
    { label: t('runtime.colGroup'), value: displayValue(person.group_name) },
    { label: t('runtime.colDepartment'), value: displayValue(person.department) },
    { label: t('runtime.colMunicipality'), value: displayValue(person.municipality) },
    { label: t('runtime.colType'), value: person.participant_type ? operationalStatusLabel(person.participant_type) : '—' },
    { label: t('runtime.colStatus'), value: person.status ? operationalStatusLabel(person.status) : '—' },
    // Solo se muestra cuando hay algo que advertir; «none» era ruido en campo.
    ...(person.duplicate_flag && person.duplicate_flag !== 'none' ? [{ label: t('runtime.colDuplicateFlag'), value: operationalStatusLabel(person.duplicate_flag) }] : []),
    ...metadataColumns(person, t),
  ];
  return <div className="runtime-participant-summary">
    <div className="runtime-participant-summary-heading"><h3>{t('runtime.participantData')}</h3>{!assignmentReady && <small>{t('runtime.confirmingAssignment')}</small>}</div>
    {/* Ficha en rejilla: se acomoda al ancho (antes era una tabla de una fila
        que se cortaba en celular, docs/150). */}
    <dl className="runtime-participant-grid">
      {columns.map((column, index) => <div key={`${column.label}-${index}`}><dt>{column.label}</dt><dd>{column.value}</dd></div>)}
    </dl>
  </div>;
}
