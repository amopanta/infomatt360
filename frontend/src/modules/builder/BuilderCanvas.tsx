import { useState } from 'react';
import type { BuilderPreviewSection } from './types';
import type { TemplateSummary } from '../records/api';
import { useI18n } from '../../i18n';
import { fieldTypeInfo } from './fieldCatalog';

const optionTypes = new Set(['SELECT', 'MULTISELECT', 'DROPDOWN', 'LIKERT_5', 'LIKERT_7', 'RATING', 'RANKING']);
const numericTypes = new Set(['NUMBER', 'INTEGER', 'DECIMAL', 'PERCENTAGE', 'CURRENCY', 'NPS', 'YEAR', 'RANGE']);
const textTypes = new Set(['TEXT', 'TEXTAREA', 'DOCUMENT_ID', 'EMAIL', 'PHONE', 'URL']);

type Props = {
  sections: BuilderPreviewSection[];
  theme: { primaryColor: string; accentColor: string; backgroundColor: string; radius: string };
  availableFields: BuilderPreviewSection['fields'];
  projectTemplates: TemplateSummary[];
  activeSectionId: string;
  onActiveSectionChange: (sectionId: string) => void;
  onSectionTitleChange: (sectionId: string, title: string) => void;
  onRemoveSection: (sectionId: string) => void;
  onFieldChange: (fieldId: string, patch: Partial<BuilderPreviewSection['fields'][number]>) => void;
  onRemoveField: (fieldId: string) => void;
  onMoveField: (sectionId: string, fromIndex: number, toIndex: number) => void;
  onPreview: () => void;
  onSave: () => void;
  saving?: boolean;
  lockedFieldIds?: Set<string>;
  lockedSectionIds?: Set<string>;
  lockTechnicalNames?: boolean;
  disableReorder?: boolean;
};

export function BuilderCanvas({
  sections,
  theme,
  availableFields,
  projectTemplates,
  activeSectionId,
  onActiveSectionChange,
  onSectionTitleChange,
  onRemoveSection,
  onFieldChange,
  onRemoveField,
  onMoveField,
  onPreview,
  onSave,
  saving = false,
  lockedFieldIds = new Set(),
  lockedSectionIds = new Set(),
  lockTechnicalNames = false,
  disableReorder = false,
}: Props) {
  const { t } = useI18n();
  const [draggedField, setDraggedField] = useState<{ sectionId: string; fieldIndex: number } | null>(null);
  const [dropTarget, setDropTarget] = useState<{ sectionId: string; fieldIndex: number } | null>(null);
  const themeVars = {
    '--form-primary': theme.primaryColor,
    '--form-accent': theme.accentColor,
    '--form-background': theme.backgroundColor,
    '--form-radius': theme.radius,
  } as React.CSSProperties;

  return (
    <section className="builder-canvas" style={themeVars}>
      <div className="builder-toolbar">
        <div>
          <h2>{t('builder.canvas.canvasTitle')}</h2>
          <p>{t('builder.canvas.canvasDescription')}</p>
        </div>
        <div className="builder-actions">
          <button type="button" onClick={onPreview}>{t('builder.canvas.preview')}</button>
          <button type="button" className="primary" onClick={onSave} disabled={saving}>{saving ? t('builder.canvas.saving') : t('builder.canvas.saveTemplate')}</button>
        </div>
      </div>
      <div className="builder-theme-preview" aria-label={t('builder.canvas.themePreviewAria')}>
        <span>{t('builder.canvas.themePreviewLabel')}</span>
        <strong style={{ color: theme.primaryColor }}>{t('builder.canvas.sectionTitlePreview')}</strong>
        {/* Solo muestra el color del botón principal; no ejecuta ninguna acción. */}
        <button type="button" tabIndex={-1} aria-hidden="true" style={{ pointerEvents: 'none' }}>{t('builder.canvas.mainButtonPreview')}</button>
      </div>
      <div className="builder-flow-legend">
        <span>{t('builder.canvas.stepGroup')}</span>
        <span>{t('builder.canvas.stepQuestion')}</span>
        <span>{t('builder.canvas.stepValidation')}</span>
        <span>{t('builder.canvas.stepSavePublish')}</span>
      </div>
      {sections.every((section) => section.fields.length === 0) ? (
        <div className="builder-empty">
          <h3>{t('builder.canvas.emptyTitle')}</h3>
          <p>{t('builder.canvas.emptyDescription')}</p>
        </div>
      ) : null}
      {sections.map((section) => (
        <article key={section.id} className={`builder-section-card ${section.id === activeSectionId ? 'active' : ''}`}>
          <header>
            <label>
              <span>{t('builder.canvas.groupSectionLabel')}</span>
              <input value={section.title} onChange={(event) => onSectionTitleChange(section.id, event.target.value)} />
            </label>
            <div>
              <button type="button" className={section.id === activeSectionId ? 'primary' : 'secondary'} onClick={() => onActiveSectionChange(section.id)}>
                {section.id === activeSectionId ? t('builder.canvas.activeGroup') : t('builder.canvas.addHere')}
              </button>
              <button type="button" className="secondary danger" disabled={sections.length <= 1 || lockedSectionIds.has(section.id)} onClick={() => onRemoveSection(section.id)}>{t('builder.canvas.deleteGroup')}</button>
            </div>
          </header>
          {section.fields.length === 0 ? (
            <p className="builder-section-empty">{t('builder.canvas.emptySectionHint')}</p>
          ) : null}
          <div className="builder-grid">
            {section.fields.map((field, fieldIndex) => (
              <div
                key={field.id}
                className={`builder-field-card ${dropTarget?.sectionId === section.id && dropTarget.fieldIndex === fieldIndex ? 'drag-target' : ''}`}
                onDragOver={(event) => {
                  if (!draggedField || draggedField.sectionId !== section.id) return;
                  event.preventDefault();
                  setDropTarget({ sectionId: section.id, fieldIndex });
                }}
                onDragLeave={() => setDropTarget(null)}
                onDrop={(event) => {
                  event.preventDefault();
                  if (draggedField?.sectionId === section.id) onMoveField(section.id, draggedField.fieldIndex, fieldIndex);
                  setDraggedField(null);
                  setDropTarget(null);
                }}
              >
                <div className="builder-field-header">
                  <span
                    className="builder-drag-handle"
                    title={t('builder.canvas.dragHint')}
                    draggable={!disableReorder}
                    onDragStart={(event) => {
                      event.dataTransfer.effectAllowed = 'move';
                      event.dataTransfer.setData('text/plain', field.id);
                      setDraggedField({ sectionId: section.id, fieldIndex });
                    }}
                    onDragEnd={() => {
                      setDraggedField(null);
                      setDropTarget(null);
                    }}
                  >
                    ⋮⋮
                  </span>
                  <strong>{field.label || t('builder.canvas.untitledQuestion')}</strong>
                  <small className="builder-field-type" title={`${t('ux.builder.typeLabel')}: ${fieldTypeInfo(field.type).label}`}>
                    <span aria-hidden="true">{fieldTypeInfo(field.type).icon}</span> {fieldTypeInfo(field.type).label}
                  </small>
                  {!disableReorder ? (
                    <span className="builder-move-buttons">
                      <button type="button" className="secondary" disabled={fieldIndex === 0} aria-label={t('ux.builder.moveUp')} title={t('ux.builder.moveUp')} onClick={() => onMoveField(section.id, fieldIndex, fieldIndex - 1)}>↑</button>
                      <button type="button" className="secondary" disabled={fieldIndex === section.fields.length - 1} aria-label={t('ux.builder.moveDown')} title={t('ux.builder.moveDown')} onClick={() => onMoveField(section.id, fieldIndex, fieldIndex + 1)}>↓</button>
                    </span>
                  ) : null}
                  <button type="button" className="secondary" disabled={lockedFieldIds.has(field.id)} title={lockedFieldIds.has(field.id) ? t('ux.builder.deleteLockedHint') : undefined} onClick={() => onRemoveField(field.id)}>{t('builder.canvas.delete')}</button>
                </div>
                <div className="builder-field-row">
                  <label>
                    <span>{t('builder.canvas.visibleLabel')}</span>
                    <input value={field.label} onChange={(event) => onFieldChange(field.id, { label: event.target.value })} />
                  </label>
                  <label>
                    <span>{t('builder.canvas.helpPlaceholder')}</span>
                    <input value={field.placeholder ?? ''} onChange={(event) => onFieldChange(field.id, { placeholder: event.target.value })} />
                  </label>
                  <label className="builder-checkbox">
                    <input type="checkbox" checked={field.required ?? false} onChange={(event) => onFieldChange(field.id, { required: event.target.checked })} />
                    {t('builder.canvas.required')}
                  </label>
                </div>
                {optionTypes.has(field.type) ? (
                  <label className="builder-wide-control">
                    <span>{t('builder.canvas.optionsPerLine')}</span>
                    <textarea value={field.optionsText ?? ''} placeholder={t('builder.canvas.optionsPlaceholder')} onChange={(event) => onFieldChange(field.id, { optionsText: event.target.value })} />
                  </label>
                ) : null}
                {field.type === 'DOCUMENT_ID' ? (
                  <details className="builder-document-panel">
                    <summary>{t('builder.canvas.documentAppearance')}</summary>
                    <div className="builder-field-row">
                      <label>
                        <span>{t('builder.canvas.allowedFormat')}</span>
                        <select value={field.documentAppearance ?? 'alphanumeric'} onChange={(event) => onFieldChange(field.id, { documentAppearance: event.target.value as BuilderPreviewSection['fields'][number]['documentAppearance'] })}>
                          <option value="numeric">{t('builder.canvas.numericOnly')}</option>
                          <option value="alphanumeric">{t('builder.canvas.alphanumeric')}</option>
                          <option value="passport">{t('builder.canvas.passport')}</option>
                          <option value="tax_id">{t('builder.canvas.taxId')}</option>
                          <option value="custom">{t('builder.canvas.customByPattern')}</option>
                        </select>
                      </label>
                      <label>
                        <span>{t('builder.canvas.customPatternLabel')}</span>
                        <input
                          value={field.pattern ?? ''}
                          disabled={(field.documentAppearance ?? 'alphanumeric') !== 'custom'}
                          placeholder={t('builder.canvas.customPatternPlaceholder')}
                          onChange={(event) => onFieldChange(field.id, { pattern: event.target.value })}
                        />
                      </label>
                    </div>
                    <p>{t('builder.canvas.documentHint')}</p>
                  </details>
                ) : null}
                {field.type === 'LINKED_SUBFORM' ? (
                  <details className="builder-linked-subform-panel">
                    <summary>{t('builder.canvas.linkedSubformTitle')}</summary>
                    <div className="builder-field-row">
                      <label>
                        <span>{t('builder.canvas.childForm')}</span>
                        <select value={field.childTemplateId ?? ''} onChange={(event) => onFieldChange(field.id, { childTemplateId: event.target.value })}>
                          <option value="">{t('builder.canvas.selectExistingTemplate')}</option>
                          {projectTemplates.map((template) => <option key={template.id} value={template.id}>{template.name} ({template.status})</option>)}
                        </select>
                      </label>
                    </div>
                    <p>{t('builder.canvas.linkedSubformHint')}</p>
                  </details>
                ) : null}
                {['PARENT_CHILD', 'LOOKUP', 'REFERENCE'].includes(field.type) ? (
                  <details className="builder-parent-child-panel">
                    <summary>{t('builder.canvas.parentChildTitle')}</summary>
                    <div className="builder-field-row">
                      <label>
                        <span>{t('builder.canvas.linkedForm')}</span>
                        <select value={field.linkedTemplateId ?? ''} onChange={(event) => onFieldChange(field.id, { linkedTemplateId: event.target.value })}>
                          <option value="">{t('builder.canvas.selectExistingTemplate')}</option>
                          {projectTemplates.map((template) => <option key={template.id} value={template.id}>{template.name} ({template.status})</option>)}
                        </select>
                      </label>
                      <label>
                        <span>{t('builder.canvas.labelFieldLabel')}</span>
                        <input value={field.labelField ?? ''} placeholder={t('builder.canvas.labelFieldPlaceholder')} onChange={(event) => onFieldChange(field.id, { labelField: event.target.value })} />
                      </label>
                    </div>
                    <p>{t('builder.canvas.parentChildHint')}</p>
                  </details>
                ) : null}
                {['TEXT', 'PHONE', 'DOCUMENT_ID'].includes(field.type) ? (
                  <details className="builder-parent-child-panel">
                    <summary>{t('builder.canvas.participantPrefill')}</summary>
                    <label>{t('builder.canvas.participantSourceField')}
                      <select value={field.participantField ?? ''} onChange={(event) => onFieldChange(field.id, { participantField: event.target.value })}>
                        <option value="">{t('builder.canvas.noPrefill')}</option>
                        {['full_name', 'document_id', 'external_code', 'phone', 'department', 'municipality', 'group_name'].map((name) =>
                          <option key={name} value={name}>{t(`builder.canvas.participantFields.${name}`)}</option>)}
                      </select>
                    </label>
                  </details>
                ) : null}
                <details className="builder-validation-panel">
                  <summary>{t('builder.canvas.validationRules')}</summary>
                  <div className="builder-field-row">
                    {numericTypes.has(field.type) ? (
                      <>
                        <label>
                          <span>{t('builder.canvas.minValue')}</span>
                          <input type="number" value={field.min ?? ''} onChange={(event) => onFieldChange(field.id, { min: event.target.value })} />
                        </label>
                        <label>
                          <span>{t('builder.canvas.maxValue')}</span>
                          <input type="number" value={field.max ?? ''} onChange={(event) => onFieldChange(field.id, { max: event.target.value })} />
                        </label>
                        {field.type === 'RANGE' ? (
                          <label>
                            <span>{t('builder.canvas.step')}</span>
                            <input type="number" value={field.step ?? ''} onChange={(event) => onFieldChange(field.id, { step: event.target.value })} />
                          </label>
                        ) : null}
                      </>
                    ) : null}
                    {textTypes.has(field.type) ? (
                      <>
                        <label>
                          <span>{t('builder.canvas.minChars')}</span>
                          <input type="number" min="0" value={field.minLength ?? ''} onChange={(event) => onFieldChange(field.id, { minLength: event.target.value })} />
                        </label>
                        <label>
                          <span>{t('builder.canvas.maxChars')}</span>
                          <input type="number" min="0" value={field.maxLength ?? ''} onChange={(event) => onFieldChange(field.id, { maxLength: event.target.value })} />
                        </label>
                        <label>
                          <span>{t('builder.canvas.patternRegex')}</span>
                          <input value={field.pattern ?? ''} placeholder={t('builder.canvas.patternPlaceholder')} onChange={(event) => onFieldChange(field.id, { pattern: event.target.value })} />
                        </label>
                      </>
                    ) : null}
                    {!numericTypes.has(field.type) && !textTypes.has(field.type) ? <p>{t('builder.canvas.builtInValidation')}</p> : null}
                  </div>
                </details>
                <details className="builder-condition-panel">
                  <summary>{t('builder.canvas.activationCondition')}</summary>
                  <div className="builder-field-row">
                    <label>
                      <span>{t('builder.canvas.showIfField')}</span>
                      <select value={field.relevantField ?? ''} onChange={(event) => onFieldChange(field.id, { relevantField: event.target.value })}>
                        <option value="">{t('builder.canvas.alwaysVisible')}</option>
                        {availableFields.filter((candidate) => candidate.id !== field.id).map((candidate) => (
                          <option key={candidate.id} value={candidate.name}>{candidate.label || candidate.name}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>{t('builder.canvas.condition')}</span>
                      <select
                        value={field.relevantOperator ?? 'equals'}
                        disabled={!field.relevantField}
                        onChange={(event) => onFieldChange(field.id, { relevantOperator: event.target.value as BuilderPreviewSection['fields'][number]['relevantOperator'] })}
                      >
                        <option value="equals">{t('builder.canvas.equalsOp')}</option>
                        <option value="not_equals">{t('builder.canvas.notEqualsOp')}</option>
                        <option value="not_empty">{t('builder.canvas.notEmptyOp')}</option>
                        <option value="empty">{t('builder.canvas.emptyOp')}</option>
                      </select>
                    </label>
                    <label>
                      <span>{t('builder.canvas.expectedValue')}</span>
                      <input
                        value={field.relevantValue ?? ''}
                        disabled={!field.relevantField || ['not_empty', 'empty'].includes(field.relevantOperator ?? '')}
                        placeholder={t('builder.canvas.expectedValuePlaceholder')}
                        onChange={(event) => onFieldChange(field.id, { relevantValue: event.target.value })}
                      />
                    </label>
                  </div>
                  <p>{t('builder.canvas.conditionHint')}</p>
                </details>
                <details className="builder-advanced-panel">
                  <summary>{t('ux.builder.advanced')}</summary>
                  <div className="builder-field-row">
                    <label>
                      <span>{t('builder.canvas.technicalName')}</span>
                      <input value={field.name} disabled={lockTechnicalNames && lockedFieldIds.has(field.id)} onChange={(event) => onFieldChange(field.id, { name: event.target.value })} />
                    </label>
                    <label>
                      <span>{t('ux.builder.typeLabel')}</span>
                      <input value={field.type} readOnly />
                    </label>
                  </div>
                  <p>{t('ux.builder.advancedHint')}</p>
                </details>
                <details className="builder-visual-panel">
                  <summary>{t('builder.canvas.visualDecoration')}</summary>
                  <div className="builder-field-row">
                    <label>
                      <span>{t('builder.canvas.visualType')}</span>
                      <select value={field.mediaType ?? 'none'} onChange={(event) => onFieldChange(field.id, { mediaType: event.target.value as BuilderPreviewSection['fields'][number]['mediaType'] })}>
                        <option value="none">{t('builder.canvas.noIcon')}</option>
                        <option value="emoji">{t('builder.canvas.emojiIcon')}</option>
                        <option value="image">{t('builder.canvas.imageUrl')}</option>
                      </select>
                    </label>
                    <label>
                      <span>{field.mediaType === 'image' ? t('builder.canvas.imageUrlLabel') : t('builder.canvas.emojiLabel')}</span>
                      <input
                        value={field.mediaValue ?? ''}
                        disabled={!field.mediaType || field.mediaType === 'none'}
                        placeholder={field.mediaType === 'image' ? 'https://...' : '🏠'}
                        onChange={(event) => onFieldChange(field.id, { mediaValue: event.target.value })}
                      />
                    </label>
                    <label>
                      <span>{t('builder.canvas.position')}</span>
                      <select
                        value={field.mediaPosition ?? 'before'}
                        disabled={!field.mediaType || field.mediaType === 'none'}
                        onChange={(event) => onFieldChange(field.id, { mediaPosition: event.target.value as BuilderPreviewSection['fields'][number]['mediaPosition'] })}
                      >
                        <option value="before">{t('builder.canvas.beforeQuestion')}</option>
                        <option value="after">{t('builder.canvas.afterQuestion')}</option>
                      </select>
                    </label>
                    <label>
                      <span>{t('builder.canvas.size')}</span>
                      <select
                        value={field.mediaSize ?? 'medium'}
                        disabled={!field.mediaType || field.mediaType === 'none'}
                        onChange={(event) => onFieldChange(field.id, { mediaSize: event.target.value as BuilderPreviewSection['fields'][number]['mediaSize'] })}
                      >
                        <option value="small">{t('builder.canvas.small')}</option>
                        <option value="medium">{t('builder.canvas.medium')}</option>
                        <option value="large">{t('builder.canvas.large')}</option>
                      </select>
                    </label>
                  </div>
                  {field.mediaType && field.mediaType !== 'none' && field.mediaValue ? (
                    <div className="builder-visual-preview">
                      <span>{t('builder.canvas.previewLabel')}</span>
                      {field.mediaType === 'image'
                        ? <img src={field.mediaValue} alt="" />
                        : <strong>{field.mediaValue}</strong>}
                    </div>
                  ) : <p>{t('builder.canvas.visualOptionalHint')}</p>}
                </details>
              </div>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
