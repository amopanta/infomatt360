import { useState } from 'react';
import type { BuilderPreviewField, BuilderPreviewSection } from './types';
import { AUTOMATIC_TYPES, fieldTypeInfo } from './fieldCatalog';
import { useI18n } from '../../i18n';

type Theme = { primaryColor: string; accentColor: string; backgroundColor: string; radius: string };

type Props = {
  title: string;
  description?: string;
  sections: BuilderPreviewSection[];
  theme: Theme;
  onClose: () => void;
};

const OPTION_TYPES = new Set(['SELECT', 'DROPDOWN', 'LIKERT_5', 'LIKERT_7', 'RATING']);
const MULTI_TYPES = new Set(['MULTISELECT', 'RANKING']);
const NUMBER_TYPES = new Set(['NUMBER', 'INTEGER', 'DECIMAL', 'PERCENTAGE', 'CURRENCY', 'NPS', 'YEAR']);
const FILE_TYPES = new Set(['FILE', 'PDF', 'MULTIFILE', 'AUDIO', 'VIDEO']);
const DATE_INPUT: Record<string, string> = { DATE: 'date', TIME: 'time', DATETIME: 'datetime-local', MONTH: 'month', WEEK: 'week' };

function options(field: BuilderPreviewField): string[] {
  return (field.optionsText ?? '').split(/\r?\n/).map((item) => item.trim()).filter(Boolean);
}

/** Misma regla que guarda el constructor en config.relevant (ver BuilderApp.fieldConfig). */
function isVisible(field: BuilderPreviewField, values: Record<string, string>): boolean {
  if (!field.relevantField) return true;
  const current = values[field.relevantField] ?? '';
  switch (field.relevantOperator ?? 'equals') {
    case 'not_equals': return current !== (field.relevantValue ?? '');
    case 'not_empty': return current !== '';
    case 'empty': return current === '';
    default: return current === (field.relevantValue ?? '');
  }
}

/**
 * Vista previa del formulario tal como lo verá quien lo llena, en ancho de
 * celular o computador. Es interactiva (para probar las condiciones de
 * visibilidad) pero no guarda nada.
 */
export function BuilderPreview({ title, description, sections, theme, onClose }: Props) {
  const { t } = useI18n();
  const [device, setDevice] = useState<'phone' | 'desktop'>('phone');
  const [values, setValues] = useState<Record<string, string>>({});
  const hasFields = sections.some((section) => section.fields.length > 0);
  const themeVars = {
    '--form-primary': theme.primaryColor,
    '--form-accent': theme.accentColor,
    '--form-background': theme.backgroundColor,
    '--form-radius': theme.radius,
  } as React.CSSProperties;

  function set(name: string, value: string) {
    setValues((current) => ({ ...current, [name]: value }));
  }

  function control(field: BuilderPreviewField) {
    const value = values[field.name] ?? '';
    if (AUTOMATIC_TYPES.has(field.type)) return <em className="builder-preview-auto">{t('ux.builder.capturedAutomatically')}</em>;
    if (field.type === 'BOOLEAN') {
      return (
        <div className="builder-preview-choices">
          {[t('ux.builder.yes'), t('ux.builder.no')].map((label, index) => (
            <label key={label}><input type="radio" name={field.id} checked={value === (index === 0 ? 'true' : 'false')} onChange={() => set(field.name, index === 0 ? 'true' : 'false')} /> {label}</label>
          ))}
        </div>
      );
    }
    if (OPTION_TYPES.has(field.type)) {
      const items = options(field);
      if (field.type === 'DROPDOWN' || items.length > 6) {
        return (
          <select value={value} onChange={(event) => set(field.name, event.target.value)}>
            <option value="">{t('ux.builder.selectPlaceholder')}</option>
            {items.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        );
      }
      return (
        <div className="builder-preview-choices">
          {items.map((item) => <label key={item}><input type="radio" name={field.id} checked={value === item} onChange={() => set(field.name, item)} /> {item}</label>)}
        </div>
      );
    }
    if (MULTI_TYPES.has(field.type)) {
      return <div className="builder-preview-choices">{options(field).map((item) => <label key={item}><input type="checkbox" /> {item}</label>)}</div>;
    }
    if (field.type === 'TEXTAREA') return <textarea rows={3} placeholder={field.placeholder} value={value} onChange={(event) => set(field.name, event.target.value)} />;
    if (NUMBER_TYPES.has(field.type)) return <input type="number" placeholder={field.placeholder} value={value} onChange={(event) => set(field.name, event.target.value)} />;
    if (field.type === 'RANGE') return <input type="range" min={field.min || 0} max={field.max || 100} step={field.step || 1} />;
    if (DATE_INPUT[field.type]) return <input type={DATE_INPUT[field.type]} value={value} onChange={(event) => set(field.name, event.target.value)} />;
    if (field.type === 'EMAIL') return <input type="email" placeholder={field.placeholder} value={value} onChange={(event) => set(field.name, event.target.value)} />;
    if (field.type === 'PHONE') return <input type="tel" placeholder={field.placeholder} value={value} onChange={(event) => set(field.name, event.target.value)} />;
    if (field.type === 'IMAGE') return <button type="button" className="builder-preview-action">📷 {t('ux.builder.takePhoto')}</button>;
    if (FILE_TYPES.has(field.type)) return <button type="button" className="builder-preview-action">📎 {t('ux.builder.attachFile')}</button>;
    if (['GPS', 'GEOTRACE', 'GEOSHAPE'].includes(field.type)) return <button type="button" className="builder-preview-action">📍 {t('ux.builder.captureLocation')}</button>;
    if (field.type === 'SIGNATURE') return <div className="builder-preview-signature">✍️ {t('ux.builder.signHere')}</div>;
    if (['TEXT', 'DOCUMENT_ID', 'URL', 'BARCODE', 'QR', 'OCR'].includes(field.type)) return <input placeholder={field.placeholder} value={value} onChange={(event) => set(field.name, event.target.value)} />;
    return <div className="builder-preview-auto">{fieldTypeInfo(field.type).icon} {fieldTypeInfo(field.type).label}</div>;
  }

  return (
    <div className="builder-preview-overlay" role="dialog" aria-modal="true" aria-label={t('ux.builder.previewTitle')} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="builder-preview-toolbar">
        <strong>{t('ux.builder.previewTitle')}</strong>
        <div role="group" aria-label={t('ux.builder.previewTitle')}>
          <button type="button" className={device === 'phone' ? 'primary' : 'secondary'} aria-pressed={device === 'phone'} onClick={() => setDevice('phone')}>📱 {t('ux.builder.previewPhone')}</button>
          <button type="button" className={device === 'desktop' ? 'primary' : 'secondary'} aria-pressed={device === 'desktop'} onClick={() => setDevice('desktop')}>🖥️ {t('ux.builder.previewDesktop')}</button>
        </div>
        <button type="button" className="secondary" onClick={onClose}>✕ {t('ux.builder.previewClose')}</button>
      </div>
      <p className="builder-preview-note">{t('ux.builder.previewNote')}</p>
      <div className={`builder-preview-device ${device}`} style={themeVars}>
        <header className="builder-preview-header">
          <h2>{title}</h2>
          {description ? <p>{description}</p> : null}
        </header>
        {!hasFields ? <p className="builder-preview-empty">{t('ux.builder.previewEmpty')}</p> : null}
        {sections.filter((section) => section.fields.length).map((section) => (
          <section key={section.id} className="builder-preview-section">
            <h3>{section.title}</h3>
            {section.fields.filter((field) => isVisible(field, values)).map((field) => (
              <div key={field.id} className="builder-preview-field">
                <span className="builder-preview-label">
                  {field.mediaType === 'emoji' && field.mediaValue ? <span aria-hidden="true">{field.mediaValue} </span> : null}
                  {field.label || field.name}
                  {field.required ? <span className="builder-preview-required" title={t('ux.builder.required')}> *</span> : null}
                </span>
                {control(field)}
              </div>
            ))}
          </section>
        ))}
        {hasFields ? <button type="button" className="builder-preview-submit">{t('ux.builder.previewSend')}</button> : null}
      </div>
    </div>
  );
}
