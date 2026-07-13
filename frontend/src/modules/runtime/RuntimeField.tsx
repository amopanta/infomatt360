import { useState } from 'react';
import { RuntimeRepeat } from './RuntimeRepeat';
import { RuntimeSignature } from './RuntimeSignature';
import { RuntimeGeoField } from './RuntimeGeoField';
import { uploadRuntimeFile } from './api';
import { normalizeOptions, parseFieldConfig, parseNumberInput } from './fieldConfig';
import type { RepeatItem, RuntimeComponent, RuntimeFileValue, RuntimeFormValue, RuntimeFormValues, RuntimeScalarValue } from './types';
import type { RuntimeGeoValue } from './geoEngine';

type Props = {
  component: RuntimeComponent;
  projectId: string;
  values: RuntimeFormValues;
  onChange: (fieldName: string, value: RuntimeFormValue) => void;
  /** El enlace publico de captura (ver publicform/) no tiene sesion, y la
   * subida de archivos exige un JWT (`uploadRuntimeFile`); por eso ahi se
   * deshabilitan los campos de archivo/firma en vez de intentar subirlos. */
  uploadsDisabled?: boolean;
};

function isEmptyValue(value: RuntimeFormValue | undefined) {
  return value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0);
}

function conditionMatches(config: ReturnType<typeof parseFieldConfig>, values: RuntimeFormValues) {
  const relevant = config.relevant;
  if (!relevant?.field) return true;
  const sourceValue = values[relevant.field];
  const sourceText = Array.isArray(sourceValue) ? sourceValue.map(String).join(',') : String(sourceValue ?? '');
  const expected = relevant.value ?? '';

  switch (relevant.operator ?? 'equals') {
    case 'not_equals':
      return sourceText !== expected;
    case 'not_empty':
      return !isEmptyValue(sourceValue);
    case 'empty':
      return isEmptyValue(sourceValue);
    case 'equals':
    default:
      return sourceText === expected;
  }
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

export function RuntimeField(props: Props) {
  const { component, projectId, values, onChange, uploadsDisabled } = props;
  const [uploadStatus, setUploadStatus] = useState('');
  const value = values[component.name] ?? '';
  const type = component.type.toUpperCase();
  const config = parseFieldConfig(component.config_json);
  const fieldId = `runtime-field-${component.id}`;

  if (!conditionMatches(config, values)) return null;

  if (type === 'REPEAT') {
    const configuredCount = config.count_field ? values[config.count_field] : config.count;
    const count = typeof configuredCount === 'number' ? configuredCount : Number(configuredCount ?? 0);
    const items = Array.isArray(value) ? value as RepeatItem[] : [];
    return (
      <RuntimeRepeat
        name={component.name}
        label={component.label}
        count={count}
        items={items}
        onChange={(nextItems) => onChange(component.name, nextItems)}
      />
    );
  }

  if (type === 'HIDDEN') return null;

  if (type === 'GPS' || type === 'GEOTRACE' || type === 'GEOSHAPE') {
    const geometry = value && typeof value === 'object' && !Array.isArray(value) && 'coordinates' in value ? value as RuntimeGeoValue : null;
    return <RuntimeGeoField id={fieldId} type={type} label={component.label} required={config.required ?? false} value={geometry} onChange={(next) => onChange(component.name, next)} />;
  }

  if (type === 'SIGNATURE') {
    if (uploadsDisabled) {
      return (
        <div className="runtime-field-group">
          <RuntimeQuestionLabel label={component.label} config={config} />
          <small className="runtime-field-unavailable">Este campo requiere iniciar sesión; no está disponible en el enlace público.</small>
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

  const fileTypes = ['FILE', 'PDF', 'MULTIFILE', 'IMAGE', 'PHOTO', 'AUDIO', 'VIDEO', 'OCR'];
  if (fileTypes.includes(type)) {
    if (uploadsDisabled) {
      return (
        <div className="runtime-field-group">
          <RuntimeQuestionLabel label={component.label} config={config} />
          <small className="runtime-field-unavailable">Este campo requiere iniciar sesión; no está disponible en el enlace público.</small>
        </div>
      );
    }
    const multiple = type === 'MULTIFILE';
    const accept = type === 'IMAGE' || type === 'PHOTO' || type === 'OCR' ? 'image/*' : type === 'AUDIO' ? 'audio/*' : type === 'VIDEO' ? 'video/*' : type === 'PDF' ? 'application/pdf' : undefined;
    const uploaded = Array.isArray(value) ? value as RuntimeFileValue[] : value && typeof value === 'object' ? [value as RuntimeFileValue] : [];

    async function uploadFiles(files: FileList | null) {
      if (!files?.length || !projectId) return;
      setUploadStatus('Cargando evidencia...');
      try {
        const results = await Promise.all(Array.from(files, (file) => uploadRuntimeFile(projectId, type, file)));
        onChange(component.name, multiple ? [...uploaded, ...results] : results[0]);
        setUploadStatus(`${results.length} archivo(s) cargado(s).`);
      } catch (error) {
        setUploadStatus(error instanceof Error ? error.message : 'Error al cargar la evidencia.');
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

  let options = normalizeOptions(config);
  if (type === 'LIKERT_5' && options.length === 0) options = Array.from({ length: 5 }, (_, index) => ({ label: String(index + 1), value: String(index + 1) }));
  if (type === 'LIKERT_7' && options.length === 0) options = Array.from({ length: 7 }, (_, index) => ({ label: String(index + 1), value: String(index + 1) }));
  if (type === 'SELECT' || type === 'DROPDOWN' || type === 'REFERENCE' || type === 'LOOKUP' || type.startsWith('LIKERT_')) {
    return (
      <label className="runtime-field-group" htmlFor={fieldId}>
        <RuntimeQuestionLabel label={component.label} config={config} />
        <select {...commonProps} value={String(scalarValue ?? '')} onChange={(event) => onChange(component.name, event.target.value || null)}>
          <option value="">Seleccione una opcion</option>
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
        title={type === 'DOCUMENT_ID' ? 'Ingrese el documento con el formato permitido.' : undefined}
        step={type === 'INTEGER' || type === 'YEAR' || type === 'NPS' ? 1 : numericTypes.includes(type) ? 'any' : undefined}
        onChange={(event) => onChange(component.name, numericTypes.includes(type) || type === 'YEAR' ? parseNumberInput(event.target.value) : event.target.value)}
      />
    </label>
  );
}
