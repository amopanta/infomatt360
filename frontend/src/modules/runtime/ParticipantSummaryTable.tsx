import type { EligibleParticipant } from './api';

type ParticipantColumn = { label: string; value: string };

const metadataLabels: Record<string, string> = {
  department: 'Departamento', departamento: 'Departamento',
  municipality: 'Municipio', municipio: 'Municipio',
  group_name: 'Grupo',
};

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return '—';
  if (Array.isArray(value)) return value.map(displayValue).join(', ');
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function metadataColumns(person: EligibleParticipant): ParticipantColumn[] {
  let metadata: unknown;
  try { metadata = JSON.parse(person.metadata_json || '{}'); } catch { return []; }
  if (!metadata || typeof metadata !== 'object' || Array.isArray(metadata)) return [];
  const ignored = new Set(['department', 'departamento', 'municipality', 'municipio', 'group_name']);
  return Object.entries(metadata).filter(([key]) => !ignored.has(key)).map(([key, value]) => ({
    label: metadataLabels[key] || key.replace(/_/g, ' ').replace(/^./, (letter) => letter.toUpperCase()),
    value: displayValue(value),
  }));
}

export function ParticipantSummaryTable({ person, assignmentReady }: { person: EligibleParticipant; assignmentReady: boolean }) {
  const columns: ParticipantColumn[] = [
    { label: 'Nombre completo', value: displayValue(person.full_name) },
    { label: 'Documento', value: displayValue(person.document_id) },
    { label: 'Código', value: displayValue(person.external_code) },
    { label: 'Grupo', value: displayValue(person.group_name) },
    { label: 'Departamento', value: displayValue(person.department) },
    { label: 'Municipio', value: displayValue(person.municipality) },
    { label: 'Tipo', value: displayValue(person.participant_type) },
    { label: 'Estado', value: displayValue(person.status) },
    { label: 'Marca de duplicado', value: displayValue(person.duplicate_flag) },
    ...metadataColumns(person),
  ];
  return <div className="runtime-participant-summary">
    <div className="runtime-participant-summary-heading"><h3>Datos del participante</h3>{!assignmentReady && <small>Confirmando asignación...</small>}</div>
    <div className="runtime-participant-summary-scroll"><table>
      <thead><tr>{columns.map((column, index) => <th key={`${column.label}-${index}`} scope="col">{column.label}</th>)}</tr></thead>
      <tbody><tr>{columns.map((column, index) => <td key={`${column.label}-${index}`}>{column.value}</td>)}</tr></tbody>
    </table></div>
  </div>;
}
