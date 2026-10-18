import { useEffect, useState } from 'react';
import { RuntimeRepeat } from './RuntimeRepeat';
import { RuntimeSignature } from './RuntimeSignature';
import { RuntimeDeviceVerification } from './RuntimeDeviceVerification';
import { RuntimeGeoField } from './RuntimeGeoField';
import { searchLinkableRecords, uploadRuntimeFile } from './api';
import { normalizeOptions, parseFieldConfig, parseNumberInput } from './fieldConfig';
import { isFieldVisible } from './formLogic';
import { evaluateXlsExpression } from './xlsExpression';
import type { RepeatItem, RuntimeComponent, RuntimeDeviceVerificationValue, RuntimeFileValue, RuntimeFormValue, RuntimeFormValues, RuntimeScalarValue } from './types';
import type { RuntimeGeoValue } from './geoEngine';
import { useI18n } from '../../i18n';

type Props = {
  component: RuntimeComponent;
  templateId: string;
  projectId: string;
  values: RuntimeFormValues;
  onChange: (fieldName: string, value: RuntimeFormValue) => void;
  /** El enlace publico de captura (ver publicform/) no tiene sesion, y la
   * subida de archivos exige un JWT (`uploadRuntimeFile`); por eso ahi se
   * deshabilitan los campos de archivo/firma en vez de intentar subirlos. */
  uploadsDisabled?: boolean;
};

/** Campos que llena el sistema; se muestran sin control editable. */
const AUTOMATIC_FIELD_TYPES = new Set(['UUID', 'RESPONSE_ID', 'SERIAL_NUMBER', 'CAPTURED_BY', 'CHANGE_HISTORY', 'INTERVIEW_DURATION']);

function isEmptyValue(value: RuntimeFormValue | undefined) {
  return value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0);
}

function RuntimeQuestionLabel({ label, config }: { label: string; config: ReturnType<typeof parseFieldConfig> }) {
  const visual = config.visual;
  const hasVisual = Boolean(visual?.type && visual.value);
  const media = hasVisual ? (
    <span className={`runtime-question-media ${visual?.type ?? ''} ${visual?.size ?? 'medium'}`} aria-hidden="true">
      {visual?.type === 'image' ? <img src={visual.value} alt="" /> : visual?.value}
    </span>
  ) : null;

  return (
    <span className={`runtime-question-label ${visual?.position === 'after' ? 'after' : 'before'}`}>
      {visual?.position !== 'after' ? media : null}
      <span>{label}</span>
      {visual?.position === 'after' ? media : null}
    </span>
  );
}

function labelForRecord(record: { id: string; values: { field_name: string; field_value_json: string }[] }, labelField?: string): string {
  const target = labelField ? record.values.find((item) => item.field_name === labelField) : undefined;
  if (!target) return record.id;
  try {
    const parsed = JSON.parse(target.field_value_json);
    return parsed === null || parsed === '' ? record.id : String(parsed);
  } catch {
    return record.id;
  }
}

/** Selector real de PARENT_CHILD (ver docs/97): busca registros existentes
 * de la plantilla enlazada y guarda el id del registro seleccionado, en vez
 * de dejar el campo como texto libre sin ninguna logica de enlace. */
function RuntimeParentChildField({ fieldId, label, config, value, required, onChange }: {
  fieldId: string;
  label: string;
  config: ReturnType<typeof parseFieldConfig>;
  value: RuntimeScalarValue;
  required: boolean;
  onChange: (next: string | null) => void;
}) {
  const { t } = useI18n();
  const [search, setSearch] = useState('');
  const [candidates, setCandidates] = useState<{ id: string; values: { field_name: string; field_value_json: string }[] }[]>([]);
  const [status, setStatus] = useState('');
  const linkedTemplateId = config.linked_template_id;

  useEffect(() => {
    if (!linkedTemplateId) return;
    let active = true;
    searchLinkableRecords(linkedTemplateId, search)
      .then((results) => { if (active) setCandidates(results); })
      .catch((error: Error) => { if (active) setStatus(error.message); });
    return () => { active = false; };
  }, [linkedTemplateId, search]);

  if (!linkedTemplateId) {
    return (
      <div className="runtime-field-group">
        <RuntimeQuestionLabel label={label} config={config} />
        <small className="runtime-field-unavailable">{t('runtime.noLinkedTemplate')}</small>
      </div>
    );
  }

  return (
    <label className="runtime-field-group" htmlFor={fieldId}>
      <RuntimeQuestionLabel label={label} config={config} />
      <input type="search" placeholder={t('runtime.searchRecord')} value={search} onChange={(event) => setSearch(event.target.value)} />
      <select id={fieldId} className="runtime-field" required={required} value={String(value ?? '')} onChange={(event) => onChange(event.target.value || null)}>
        <option value="">{t('runtime.selectLinkedRecord')}</option>
        {candidates.map((candidate) => <option key={candidate.id} value={candidate.id}>{labelForRecord(candidate, config.label_field)}</option>)}
      </select>
      {status ? <small role="status">{status}</small> : null}
    </label>
  );
}

export function RuntimeField(props: Props) {
  const { t } = useI18n();
  const { component, templateId, projectId, values, onChange, uploadsDisabled } = props;
  const [uploadStatus, setUploadStatus] = useState('');
  const value = values[component.name] ?? '';
  const type = component.type.toUpperCase();
  const config = parseFieldConfig(component.config_json);
  const fieldId = `runtime-field-${component.id}`;

  if (!isFieldVisible(component, values)) return null;

  if (type === 'REPEAT') {
    // Con count_field/count el número de filas lo fija el formulario; sin
    // ellos, la persona agrega y quita filas (repeat de XLSForm sin repeat_count).
    const configuredCount = config.count_field ? values[config.count_field] : config.count;
    const fixedCount = configuredCount === undefined || configuredCount === null || configuredCount === ''
      ? null
      : Number.isFinite(Number(configuredCount)) ? Number(configuredCount) : 0;
    const items = Array.isArray(value) ? value as RepeatItem[] : [];
    const rawConfig = config as Record<string, unknown>;
    return (
      <RuntimeRepeat
        name={component.name}
        label={component.label}
        fields={rawConfig.fields}
        fixedCount={fixedCount}
        minRows={typeof rawConfig.min_repeats === 'number' ? rawConfig.min_repeats : config.required ? 1 : 0}
        maxRows={typeof rawConfig.max_repeats === 'number' ? rawConfig.max_repeats : undefined}
        items={items}
        onChange={(nextItems) => onChange(component.name, nextItems)}
        templateId={templateId}
        projectId={projectId}
        uploadsDisabled={uploadsDisabled}
      />
    );
  }

  if (type === 'HIDDEN') return null;

  if (config.calculation) return <label className="runtime-field-group" htmlFor={fieldId}><RuntimeQuestionLabel label={component.label} config={config} /><input id={fieldId} className="runtime-field" value={String(value ?? '')} readOnly /><small>{t('runtime.autoCalculated')}</small></label>;

  // Los llena el servidor (o el envío, en INTERVIEW_DURATION): quien captura
  // no debe poder escribirlos, p. ej. poner otro nombre en "Quién lo llenó".
  if (AUTOMATIC_FIELD_TYPES.has(type)) {
    return (
      <div className="runtime-field-group runtime-field-automatic">
        <RuntimeQuestionLabel label={component.label} config={config} />
        <small>{isEmptyValue(value) || typeof value === 'object' ? t('ux.runtime.automatic') : String(value)}</small>
      </div>
    );
  }

  if (type === 'LINKED_SUBFORM') {
    return (
      <div className="runtime-field-group">
        <RuntimeQuestionLabel label={component.label} config={config} />
        <small className="runtime-field-unavailable">{t('runtime.linkedSubformHint')}</small>
      </div>
    );
  }

  if (type === 'PARENT_CHILD' || (['LOOKUP', 'REFERENCE'].includes(type) && config.linked_template_id)) {
    return (
      <RuntimeParentChildField
        fieldId={fieldId}
        label={component.label}
        config={config}
        value={value as RuntimeScalarValue}
        required={config.required ?? false}
        onChange={(next) => onChange(component.name, next)}
      />
    );
  }

  if (type === 'GPS' || type === 'GEOTRACE' || type === 'GEOSHAPE') {
    const geometry = value && typeof value === 'object' && !Array.isArray(value) && 'coordinates' in value ? value as RuntimeGeoValue : null;
    return <RuntimeGeoField id={fieldId} type={type} label={component.label} required={config.required ?? false} value={geometry} onChange={(next) => onChange(component.name, next)} />;
  }

  if (type === 'SIGNATURE') {
    if (uploadsDisabled) {
      return (
        <div className="runtime-field-group">
          <RuntimeQuestionLabel label={component.label} config={config} />
          <small className="runtime-field-unavailable">{t('runtime.requiresLogin')}</small>
        </div>
      );
    }
    const signature = value && typeof value === 'object' && !Array.isArray(value) ? value as RuntimeFileValue : null;
    return (
      <RuntimeSignature
        id={fieldId}
        name={component.name}
        label={component.label}
        projectId={projectId}
        required={config.required ?? false}
        value={signature}
        onChange={(uploaded) => onChange(component.name, uploaded)}
      />
    );
  }

  if (type === 'FINGERPRINT') {
    if (uploadsDisabled) return <div className="runtime-field-group"><RuntimeQuestionLabel label={component.label} config={config} /><small>{t('runtime.deviceVerificationRequiresLogin')}</small></div>;
    return <RuntimeDeviceVerification
      id={fieldId} componentId={component.id} templateId={templateId}
      label={component.label} required={config.required ?? false}
      value={value && typeof value === 'object' && !Array.isArray(value) && 'method' in value && value.method === 'device_user_verification' ? value as RuntimeDeviceVerificationValue : null}
      onChange={(proof) => onChange(component.name, proof)}
    />;
  }

  const fileTypes = ['FILE', 'PDF', 'MULTIFILE', 'IMAGE', 'PHOTO', 'AUDIO', 'VIDEO', 'OCR'];
  if (fileTypes.includes(type)) {
    if (uploadsDisabled) {
      return (
        <div className="runtime-field-group">
          <RuntimeQuestionLabel label={component.label} config={config} />
          <small className="runtime-field-unavailable">{t('runtime.requiresLogin')}</small>
        </div>
      );
    }
    const multiple = type === 'MULTIFILE';
    const accept = type === 'IMAGE' || type === 'PHOTO' || type === 'FINGERPRINT' || type === 'OCR' ? 'image/*' : type === 'AUDIO' ? 'audio/*' : type === 'VIDEO' ? 'video/*' : type === 'PDF' ? 'application/pdf' : undefined;
    const uploaded = Array.isArray(value) ? value as RuntimeFileValue[] : value && typeof value === 'object' ? [value as RuntimeFileValue] : [];

    async function uploadFiles(files: FileList | null) {
      if (!files?.length || !projectId) return;
      setUploadStatus(t('runtime.uploadingEvidence'));
      try {
        const results = await Promise.all(Array.from(files, (file) => uploadRuntimeFile(projectId, type, file)));
        onChange(component.name, multiple ? [...uploaded, ...results] : results[0]);
        setUploadStatus(t('runtime.filesUploaded', { count: results.length }));
      } catch (error) {
        setUploadStatus(error instanceof Error ? error.message : t('runtime.uploadError'));
      }
    }

    return (
      <label className="runtime-field-group" htmlFor={fieldId}>
        <RuntimeQuestionLabel label={component.label} config={config} />
        <input id={fieldId} name={component.name} className="runtime-field" type="file" accept={accept} multiple={multiple} required={config.required && uploaded.length === 0} onChange={(event) => void uploadFiles(event.target.files)} />
        {uploaded.map((file) => <small key={file.file_asset_id}>{file.name} ({file.size_bytes} bytes)</small>)}
        {uploadStatus ? <small role="status">{uploadStatus}</small> : null}
      </label>
    );
  }

  const scalarValue = value as RuntimeScalarValue;
  const commonProps = {
    id: fieldId,
    name: component.name,
    className: 'runtime-field',
    required: config.required ?? false,
  };

  if (type === 'BOOLEAN') {
    return (
      <label className="runtime-boolean" htmlFor={fieldId}>
        <input
          {...commonProps}
          type="checkbox"
          checked={value === true}
          onChange={(event) => onChange(component.name, event.target.checked)}
        />
        <RuntimeQuestionLabel label={component.label} config={config} />
      </label>
    );
  }

  let options = config.choice_filter && Array.isArray(config.options)
    ? normalizeOptions({ options: config.options.filter((option) => {
      if (typeof option !== 'object' || option === null || Array.isArray(option)) return false;
      try { return Boolean(evaluateXlsExpression(config.choice_filter!, values, option as Record<string, unknown>)); }
      catch { return true; }
    }) })
    : normalizeOptions(config);
  if (type === 'LIKERT_5' && options.length === 0) options = Array.from({ length: 5 }, (_, index) => ({ label: String(index + 1), value: String(index + 1) }));
  if (type === 'LIKERT_7' && options.length === 0) options = Array.from({ length: 7 }, (_, index) => ({ label: String(index + 1), value: String(index + 1) }));

  if (type === 'RATING' || type === 'NPS') {
    // Escala de botones: RATING 1..5 (o sus opciones), NPS 0..10. Se guarda el número.
    const scale = options.length
      ? options.map((option) => Number(option.value)).filter(Number.isFinite)
      : type === 'NPS' ? Array.from({ length: 11 }, (_, index) => index) : [1, 2, 3, 4, 5];
    const current = typeof value === 'number' ? value : value === '' || value === null ? null : Number(value);
    const max = Math.max(...scale);
    return (
      <div className="runtime-field-group" role="group" aria-labelledby={`${fieldId}-label`}>
        <span id={`${fieldId}-label`}><RuntimeQuestionLabel label={component.label} config={config} /></span>
        <div className={`runtime-scale ${type === 'RATING' ? 'stars' : ''}`}>
          {scale.map((point) => (
            <button
              key={point}
              type="button"
              aria-pressed={current === point}
              aria-label={t('ux.runtime.ratingLabel', { value: point, max })}
              className={current !== null && (type === 'RATING' ? point <= current : point === current) ? 'active' : ''}
              onClick={() => onChange(component.name, current === point ? null : point)}
            >
              {type === 'RATING' ? '★' : point}
            </button>
          ))}
        </div>
      </div>
    );
  }

  if (type === 'RANKING') {
    // Se guarda la lista de valores en el orden elegido (primero = más importante).
    const order = Array.isArray(value) && value.length ? (value as string[]) : options.map((option) => option.value);
    const byValue = new Map(options.map((option) => [option.value, option.label]));
    const move = (from: number, to: number) => {
      const next = [...order];
      const [moved] = next.splice(from, 1);
      next.splice(to, 0, moved);
      onChange(component.name, next);
    };
    return (
      <div className="runtime-field-group">
        <RuntimeQuestionLabel label={component.label} config={config} />
        <small>{t('ux.runtime.rankHint')}</small>
        <ol className="runtime-ranking">
          {order.map((item, index) => (
            <li key={item}>
              <span>{byValue.get(item) ?? item}</span>
              <button type="button" aria-label={t('ux.runtime.moveUp')} disabled={index === 0} onClick={() => move(index, index - 1)}>↑</button>
              <button type="button" aria-label={t('ux.runtime.moveDown')} disabled={index === order.length - 1} onClick={() => move(index, index + 1)}>↓</button>
            </li>
          ))}
        </ol>
      </div>
    );
  }

  if (type === 'MATRIX') {
    // Filas en config.rows y escala en config.options; valor { fila: opción }.
    const rows = normalizeOptions({ options: (config as Record<string, unknown>).rows } as Parameters<typeof normalizeOptions>[0]);
    const scaleOptions = options.length ? options : [1, 2, 3, 4, 5].map((point) => ({ value: String(point), label: String(point) }));
    if (rows.length === 0) {
      return (
        <div className="runtime-field-group">
          <RuntimeQuestionLabel label={component.label} config={config} />
          <small className="runtime-field-unavailable">{t('ux.runtime.matrixWithoutRows')}</small>
        </div>
      );
    }
    const answers = value && typeof value === 'object' && !Array.isArray(value) ? value as unknown as Record<string, string> : {};
    return (
      <fieldset className="runtime-field-group runtime-matrix">
        <legend><RuntimeQuestionLabel label={component.label} config={config} /></legend>
        <table>
          <thead><tr><th />{scaleOptions.map((option) => <th key={option.value}>{option.label}</th>)}</tr></thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.value}>
                <th scope="row">{row.label}</th>
                {scaleOptions.map((option) => (
                  <td key={option.value}>
                    <input
                      type="radio"
                      name={`${fieldId}-${row.value}`}
                      aria-label={`${row.label}: ${option.label}`}
                      checked={answers[row.value] === option.value}
                      onChange={() => onChange(component.name, { ...answers, [row.value]: option.value } as unknown as RuntimeFormValue)}
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </fieldset>
    );
  }
  if (type === 'SELECT' || type === 'DROPDOWN' || type === 'REFERENCE' || type === 'LOOKUP' || type.startsWith('LIKERT_')) {
    return (
      <label className="runtime-field-group" htmlFor={fieldId}>
        <RuntimeQuestionLabel label={component.label} config={config} />
        <select {...commonProps} value={String(scalarValue ?? '')} onChange={(event) => onChange(component.name, event.target.value || null)}>
          <option value="">{t('runtime.selectOption')}</option>
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
    );
  }

  if (type === 'MULTISELECT') {
    const selectedValues = Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
    return (
      <label className="runtime-field-group" htmlFor={fieldId}>
        <RuntimeQuestionLabel label={component.label} config={config} />
        <select
          {...commonProps}
          multiple
          value={selectedValues}
          onChange={(event) => onChange(component.name, Array.from(event.target.selectedOptions, (option) => option.value))}
        >
          {options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
        </select>
      </label>
    );
  }

  if (type === 'TEXTAREA') {
    return (
      <label className="runtime-field-group" htmlFor={fieldId}>
        <RuntimeQuestionLabel label={component.label} config={config} />
        <textarea
          {...commonProps}
          placeholder={config.placeholder}
          minLength={config.min_length}
          maxLength={config.max_length}
          value={String(scalarValue ?? '')}
          onChange={(event) => onChange(component.name, event.target.value)}
        />
      </label>
    );
  }

  if (type === 'RANGE') {
    const min = config.min ?? 0;
    const max = config.max ?? 100;
    const step = config.step ?? 1;
    const rangeValue = isEmptyValue(value) ? min : (scalarValue as number);
    return (
      <label className="runtime-field-group" htmlFor={fieldId}>
        <RuntimeQuestionLabel label={component.label} config={config} />
        <input
          {...commonProps}
          type="range"
          min={min}
          max={max}
          step={step}
          value={String(rangeValue)}
          onChange={(event) => onChange(component.name, parseNumberInput(event.target.value))}
        />
        <output htmlFor={fieldId}>{String(rangeValue)}</output>
      </label>
    );
  }

  const numericTypes = ['NUMBER', 'INTEGER', 'DECIMAL', 'PERCENTAGE', 'CURRENCY', 'NPS'];
  const inputType = numericTypes.includes(type) ? 'number'
    : type === 'DATE' ? 'date'
      : type === 'TIME' ? 'time'
        : type === 'DATETIME' ? 'datetime-local'
          : type === 'MONTH' ? 'month'
            : type === 'WEEK' ? 'week'
              : type === 'EMAIL' ? 'email'
                : type === 'PHONE' ? 'tel'
                  : type === 'URL' ? 'url'
                    : 'text';
  const documentInputMode = type === 'DOCUMENT_ID' && config.document_appearance === 'numeric' ? 'numeric' : undefined;
  return (
    <label className="runtime-field-group" htmlFor={fieldId}>
      <RuntimeQuestionLabel label={component.label} config={config} />
      <input
        {...commonProps}
        type={inputType}
        placeholder={config.placeholder}
        value={String(scalarValue ?? '')}
        min={config.min ?? (type === 'PERCENTAGE' || type === 'NPS' ? 0 : undefined)}
        max={config.max ?? (type === 'PERCENTAGE' ? 100 : type === 'NPS' ? 10 : undefined)}
        minLength={config.min_length}
        maxLength={config.max_length}
        pattern={config.pattern}
        inputMode={documentInputMode}
        title={type === 'DOCUMENT_ID' ? t('runtime.enterDocumentFormat') : undefined}
        step={type === 'INTEGER' || type === 'YEAR' || type === 'NPS' ? 1 : numericTypes.includes(type) ? 'any' : undefined}
        onChange={(event) => onChange(component.name, numericTypes.includes(type) || type === 'YEAR' ? parseNumberInput(event.target.value) : event.target.value)}
      />
    </label>
  );
}
