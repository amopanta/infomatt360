import { useState } from 'react';
import type { BuilderPreviewSection } from './types';

const optionTypes = new Set(['SELECT', 'MULTISELECT', 'DROPDOWN', 'LIKERT_5', 'LIKERT_7', 'RATING', 'RANKING']);
const numericTypes = new Set(['NUMBER', 'INTEGER', 'DECIMAL', 'PERCENTAGE', 'CURRENCY', 'NPS', 'YEAR']);
const textTypes = new Set(['TEXT', 'TEXTAREA', 'DOCUMENT_ID', 'EMAIL', 'PHONE', 'URL']);

type Props = {
  sections: BuilderPreviewSection[];
  theme: { primaryColor: string; accentColor: string; backgroundColor: string; radius: string };
  availableFields: BuilderPreviewSection['fields'];
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
};

export function BuilderCanvas({
  sections,
  theme,
  availableFields,
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
}: Props) {
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
          <h2>Lienzo del formulario</h2>
          <p>Construye por grupos: cada bloque equivale a una seccion de captura como en KoboToolbox/LimeSurvey.</p>
        </div>
        <div className="builder-actions">
          <button type="button" onClick={onPreview}>Vista previa</button>
          <button type="button" className="primary" onClick={onSave} disabled={saving}>{saving ? 'Guardando...' : 'Guardar plantilla'}</button>
        </div>
      </div>
      <div className="builder-theme-preview" aria-label="Vista previa del tema visual">
        <span>Vista del tema elegido</span>
        <strong style={{ color: theme.primaryColor }}>Titulo de seccion</strong>
        <button type="button">Boton principal</button>
      </div>
      <div className="builder-flow-legend">
        <span>1. Grupo</span>
        <span>2. Pregunta</span>
        <span>3. Validacion</span>
        <span>4. Guardar/Publicar</span>
      </div>
      {sections.every((section) => section.fields.length === 0) ? (
        <div className="builder-empty">
          <h3>Tu plantilla aun no tiene preguntas</h3>
          <p>Haz clic en un componente de la paleta para agregar la primera pregunta.</p>
        </div>
      ) : null}
      {sections.map((section) => (
        <article key={section.id} className={`builder-section-card ${section.id === activeSectionId ? 'active' : ''}`}>
          <header>
            <label>
              <span>Nombre del grupo / seccion</span>
              <input value={section.title} onChange={(event) => onSectionTitleChange(section.id, event.target.value)} />
            </label>
            <div>
              <button type="button" className={section.id === activeSectionId ? 'primary' : 'secondary'} onClick={() => onActiveSectionChange(section.id)}>
                {section.id === activeSectionId ? 'Grupo activo' : 'Agregar aqui'}
              </button>
              <button type="button" className="secondary danger" disabled={sections.length <= 1} onClick={() => onRemoveSection(section.id)}>Eliminar grupo</button>
            </div>
          </header>
          {section.fields.length === 0 ? (
            <p className="builder-section-empty">Este grupo aun no tiene preguntas. Seleccionalo como grupo activo y haz clic en un tipo de pregunta.</p>
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
                    title="Arrastra para cambiar el orden"
                    draggable
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
                  <strong>{field.label || 'Pregunta sin titulo'}</strong>
                  <small>{field.type}</small>
                  <button type="button" className="secondary" onClick={() => onRemoveField(field.id)}>Eliminar</button>
                </div>
                <div className="builder-field-row">
                  <label>
                    <span>Etiqueta visible</span>
                    <input value={field.label} onChange={(event) => onFieldChange(field.id, { label: event.target.value })} />
                  </label>
                  <label>
                    <span>Nombre tecnico</span>
                    <input value={field.name} onChange={(event) => onFieldChange(field.id, { name: event.target.value })} />
                  </label>
                  <label>
                    <span>Ayuda / placeholder</span>
                    <input value={field.placeholder ?? ''} onChange={(event) => onFieldChange(field.id, { placeholder: event.target.value })} />
                  </label>
                  <label className="builder-checkbox">
                    <input type="checkbox" checked={field.required ?? false} onChange={(event) => onFieldChange(field.id, { required: event.target.checked })} />
                    Obligatorio
                  </label>
                </div>
                {optionTypes.has(field.type) ? (
                  <label className="builder-wide-control">
                    <span>Opciones, una por linea</span>
                    <textarea value={field.optionsText ?? ''} placeholder={'Opcion 1\nOpcion 2\nOpcion 3'} onChange={(event) => onFieldChange(field.id, { optionsText: event.target.value })} />
                  </label>
                ) : null}
                {field.type === 'DOCUMENT_ID' ? (
                  <details className="builder-document-panel">
                    <summary>Apariencia del documento</summary>
                    <div className="builder-field-row">
                      <label>
                        <span>Formato permitido</span>
                        <select value={field.documentAppearance ?? 'alphanumeric'} onChange={(event) => onFieldChange(field.id, { documentAppearance: event.target.value as BuilderPreviewSection['fields'][number]['documentAppearance'] })}>
                          <option value="numeric">Solo numeros: cedula o DNI</option>
                          <option value="alphanumeric">Letras y numeros: extranjeria</option>
                          <option value="passport">Pasaporte: letras, numeros y guion</option>
                          <option value="tax_id">NIT/RUT: numeros, letras, punto y guion</option>
                          <option value="custom">Personalizado por patron</option>
                        </select>
                      </label>
                      <label>
                        <span>Patron personalizado</span>
                        <input
                          value={field.pattern ?? ''}
                          disabled={(field.documentAppearance ?? 'alphanumeric') !== 'custom'}
                          placeholder="Ej: ^[A-Z]{2}[0-9]{6}$"
                          onChange={(event) => onFieldChange(field.id, { pattern: event.target.value })}
                        />
                      </label>
                    </div>
                    <p>Se guarda como texto controlado para conservar letras, numeros y ceros iniciales.</p>
                  </details>
                ) : null}
                <details className="builder-validation-panel">
                  <summary>Reglas de validacion</summary>
                  <div className="builder-field-row">
                    {numericTypes.has(field.type) ? (
                      <>
                        <label>
                          <span>Valor minimo</span>
                          <input type="number" value={field.min ?? ''} onChange={(event) => onFieldChange(field.id, { min: event.target.value })} />
                        </label>
                        <label>
                          <span>Valor maximo</span>
                          <input type="number" value={field.max ?? ''} onChange={(event) => onFieldChange(field.id, { max: event.target.value })} />
                        </label>
                      </>
                    ) : null}
                    {textTypes.has(field.type) ? (
                      <>
                        <label>
                          <span>Min. caracteres</span>
                          <input type="number" min="0" value={field.minLength ?? ''} onChange={(event) => onFieldChange(field.id, { minLength: event.target.value })} />
                        </label>
                        <label>
                          <span>Max. caracteres</span>
                          <input type="number" min="0" value={field.maxLength ?? ''} onChange={(event) => onFieldChange(field.id, { maxLength: event.target.value })} />
                        </label>
                        <label>
                          <span>Patron / regex</span>
                          <input value={field.pattern ?? ''} placeholder="Ej: ^[0-9]+$" onChange={(event) => onFieldChange(field.id, { pattern: event.target.value })} />
                        </label>
                      </>
                    ) : null}
                    {!numericTypes.has(field.type) && !textTypes.has(field.type) ? <p>Este tipo usa validaciones propias del campo.</p> : null}
                  </div>
                </details>
                <details className="builder-condition-panel">
                  <summary>Condicion de activacion</summary>
                  <div className="builder-field-row">
                    <label>
                      <span>Mostrar si este campo</span>
                      <select value={field.relevantField ?? ''} onChange={(event) => onFieldChange(field.id, { relevantField: event.target.value })}>
                        <option value="">Siempre visible</option>
                        {availableFields.filter((candidate) => candidate.id !== field.id).map((candidate) => (
                          <option key={candidate.id} value={candidate.name}>{candidate.label || candidate.name}</option>
                        ))}
                      </select>
                    </label>
                    <label>
                      <span>Condicion</span>
                      <select
                        value={field.relevantOperator ?? 'equals'}
                        disabled={!field.relevantField}
                        onChange={(event) => onFieldChange(field.id, { relevantOperator: event.target.value as BuilderPreviewSection['fields'][number]['relevantOperator'] })}
                      >
                        <option value="equals">es igual a</option>
                        <option value="not_equals">es diferente de</option>
                        <option value="not_empty">tiene respuesta</option>
                        <option value="empty">esta vacio</option>
                      </select>
                    </label>
                    <label>
                      <span>Valor esperado</span>
                      <input
                        value={field.relevantValue ?? ''}
                        disabled={!field.relevantField || ['not_empty', 'empty'].includes(field.relevantOperator ?? '')}
                        placeholder="Ej: si, 1, opcion_1"
                        onChange={(event) => onFieldChange(field.id, { relevantValue: event.target.value })}
                      />
                    </label>
                  </div>
                  <p>La pregunta se ocultara en Runtime si la condicion no se cumple.</p>
                </details>
                <details className="builder-visual-panel">
                  <summary>Decoracion visual</summary>
                  <div className="builder-field-row">
                    <label>
                      <span>Tipo visual</span>
                      <select value={field.mediaType ?? 'none'} onChange={(event) => onFieldChange(field.id, { mediaType: event.target.value as BuilderPreviewSection['fields'][number]['mediaType'] })}>
                        <option value="none">Sin icono/imagen</option>
                        <option value="emoji">Icono emoji</option>
                        <option value="image">Imagen por URL</option>
                      </select>
                    </label>
                    <label>
                      <span>{field.mediaType === 'image' ? 'URL de imagen' : 'Emoji o icono'}</span>
                      <input
                        value={field.mediaValue ?? ''}
                        disabled={!field.mediaType || field.mediaType === 'none'}
                        placeholder={field.mediaType === 'image' ? 'https://...' : '🏠'}
                        onChange={(event) => onFieldChange(field.id, { mediaValue: event.target.value })}
                      />
                    </label>
                    <label>
                      <span>Posicion</span>
                      <select
                        value={field.mediaPosition ?? 'before'}
                        disabled={!field.mediaType || field.mediaType === 'none'}
                        onChange={(event) => onFieldChange(field.id, { mediaPosition: event.target.value as BuilderPreviewSection['fields'][number]['mediaPosition'] })}
                      >
                        <option value="before">Antes de la pregunta</option>
                        <option value="after">Despues de la pregunta</option>
                      </select>
                    </label>
                    <label>
                      <span>Tamano</span>
                      <select
                        value={field.mediaSize ?? 'medium'}
                        disabled={!field.mediaType || field.mediaType === 'none'}
                        onChange={(event) => onFieldChange(field.id, { mediaSize: event.target.value as BuilderPreviewSection['fields'][number]['mediaSize'] })}
                      >
                        <option value="small">Pequeno</option>
                        <option value="medium">Mediano</option>
                        <option value="large">Grande</option>
                      </select>
                    </label>
                  </div>
                  {field.mediaType && field.mediaType !== 'none' && field.mediaValue ? (
                    <div className="builder-visual-preview">
                      <span>Vista previa:</span>
                      {field.mediaType === 'image'
                        ? <img src={field.mediaValue} alt="" />
                        : <strong>{field.mediaValue}</strong>}
                    </div>
                  ) : <p>Opcional: agrega un icono o imagen para hacer mas clara la pregunta.</p>}
                </details>
              </div>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
