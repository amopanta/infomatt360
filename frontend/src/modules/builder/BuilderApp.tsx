import { useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { BuilderCanvas } from './BuilderCanvas';
import { BuilderPalette } from './BuilderPalette';
import type { BuilderPaletteItem, BuilderPreviewField, BuilderPreviewSection } from './types';
import { createColumn, createComponent, createPage, createRow, createSection, createTemplate } from './api';
import { createDefaultCharacterizationTemplate } from './createDefaultTemplate';

function slugify(value: string) {
  const normalized = value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '');
  const slug = normalized.replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  return slug || 'campo';
}

function uniqueName(base: string, fields: BuilderPreviewField[]) {
  let candidate = base;
  let index = 2;
  while (fields.some((field) => field.name === candidate)) {
    candidate = `${base}_${index}`;
    index += 1;
  }
  return candidate;
}

function optionsFromText(value?: string) {
  return (value ?? '')
    .split(/\r?\n/)
    .map((item) => item.trim())
    .filter(Boolean)
    .map((item) => ({ label: item, value: slugify(item) }));
}

function defaultOptionsText(type: string) {
  if (type === 'BOOLEAN') return '';
  if (type === 'LIKERT_5') return '1\n2\n3\n4\n5';
  if (type === 'LIKERT_7') return '1\n2\n3\n4\n5\n6\n7';
  if (type === 'RATING') return '1\n2\n3\n4\n5';
  if (['SELECT', 'MULTISELECT', 'DROPDOWN', 'RANKING'].includes(type)) return 'Opcion 1\nOpcion 2\nOpcion 3';
  return '';
}

function optionalNumber(value?: string) {
  if (!value?.trim()) return undefined;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function documentPattern(appearance?: BuilderPreviewField['documentAppearance'], customPattern?: string) {
  if (appearance === 'custom') return customPattern?.trim() || undefined;
  if (appearance === 'numeric') return '^[0-9]+$';
  if (appearance === 'passport') return '^[A-Za-z0-9-]+$';
  if (appearance === 'tax_id') return '^[0-9A-Za-z.-]+$';
  if (appearance === 'alphanumeric') return '^[A-Za-z0-9]+$';
  return customPattern?.trim() || undefined;
}

const initialSections: BuilderPreviewSection[] = [{ id: 'general', title: 'Informacion General', fields: [] }];

export function BuilderApp() {
  const [message, setMessage] = useState('');
  const [runtimeUrl, setRuntimeUrl] = useState('');
  const [templateName, setTemplateName] = useState('Nueva plantilla');
  const [templateDescription, setTemplateDescription] = useState('');
  const [theme, setTheme] = useState({ primaryColor: '#0066cc', accentColor: '#00c2ff', backgroundColor: '#ffffff', radius: '18px' });
  const [sections, setSections] = useState<BuilderPreviewSection[]>(initialSections);
  const [activeSectionId, setActiveSectionId] = useState(initialSections[0].id);
  const [saving, setSaving] = useState(false);
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';

  function resetTemplate() {
    const sectionId = crypto.randomUUID();
    setTemplateName('Nueva plantilla');
    setTemplateDescription('');
    setTheme({ primaryColor: '#0066cc', accentColor: '#00c2ff', backgroundColor: '#ffffff', radius: '18px' });
    setSections([{ id: sectionId, title: 'Informacion General', fields: [] }]);
    setActiveSectionId(sectionId);
    setRuntimeUrl('');
    setMessage('Plantilla nueva lista. Agrega preguntas desde la paleta.');
  }

  function addField(item: BuilderPaletteItem) {
    setSections((currentSections) => {
      const allFields = currentSections.flatMap((section) => section.fields);
      const name = uniqueName(slugify(item.label), allFields);
      const field: BuilderPreviewField = {
        id: crypto.randomUUID(),
        type: item.type,
        name,
        label: item.label,
        placeholder: item.description,
        required: false,
        optionsText: defaultOptionsText(item.type),
      };
      const nextSections = currentSections.length ? [...currentSections] : [{ id: 'general', title: 'Informacion General', fields: [] }];
      const targetIndex = Math.max(0, nextSections.findIndex((section) => section.id === activeSectionId));
      nextSections[targetIndex] = { ...nextSections[targetIndex], fields: [...nextSections[targetIndex].fields, field] };
      return nextSections;
    });
    setMessage(`Pregunta agregada: ${item.label}`);
  }

  function addSection() {
    const nextNumber = sections.length + 1;
    const section = { id: crypto.randomUUID(), title: `Grupo ${nextNumber}`, fields: [] };
    setSections((currentSections) => [...currentSections, section]);
    setActiveSectionId(section.id);
    setMessage(`Grupo creado: ${section.title}. Las nuevas preguntas se agregaran alli.`);
  }

  function updateSection(sectionId: string, title: string) {
    setSections((currentSections) => currentSections.map((section) => (
      section.id === sectionId ? { ...section, title } : section
    )));
  }

  function removeSection(sectionId: string) {
    setSections((currentSections) => {
      if (currentSections.length <= 1) return currentSections;
      const nextSections = currentSections.filter((section) => section.id !== sectionId);
      if (activeSectionId === sectionId) setActiveSectionId(nextSections[0]?.id ?? '');
      return nextSections;
    });
  }

  function updateField(fieldId: string, patch: Partial<BuilderPreviewField>) {
    setSections((currentSections) => currentSections.map((section) => ({
      ...section,
      fields: section.fields.map((field) => field.id === fieldId ? { ...field, ...patch } : field),
    })));
  }

  function removeField(fieldId: string) {
    setSections((currentSections) => currentSections.map((section) => ({
      ...section,
      fields: section.fields.filter((field) => field.id !== fieldId),
    })));
  }

  function moveField(sectionId: string, fromIndex: number, toIndex: number) {
    if (fromIndex === toIndex || fromIndex < 0 || toIndex < 0) return;
    setSections((currentSections) => currentSections.map((section) => {
      if (section.id !== sectionId) return section;
      const nextFields = [...section.fields];
      const [movedField] = nextFields.splice(fromIndex, 1);
      if (!movedField) return section;
      nextFields.splice(toIndex, 0, movedField);
      return { ...section, fields: nextFields };
    }));
    setMessage('Orden de preguntas actualizado. Recuerda guardar la plantilla para publicar este orden.');
  }

  async function saveTemplate() {
    if (!projectId) {
      setMessage('Falta proyecto activo en la sesion.');
      return;
    }
    const fields = sections.flatMap((section) => section.fields);
    if (!fields.length) {
      setMessage('Agrega al menos una pregunta antes de guardar.');
      return;
    }
    setSaving(true);
    setMessage('Guardando plantilla...');
    try {
      const template = await createTemplate({ projectId, name: templateName.trim() || 'Nueva plantilla', description: templateDescription || undefined, status: 'published', themeJson: JSON.stringify(theme) });
      let sortOrder = 1;
      const usedNames = new Set<string>();
      for (const sectionDraft of sections) {
        const page = await createPage({ templateId: template.id, title: sectionDraft.title || 'Pagina 1', sortOrder });
        const section = await createSection({ pageId: page.id, title: sectionDraft.title || 'Seccion 1', sortOrder });
        for (const field of sectionDraft.fields) {
          const row = await createRow({ sectionId: section.id, sortOrder });
          const column = await createColumn({ rowId: row.id, desktopWidth: 12, sortOrder: 1 });
          await createComponent({
            templateId: template.id,
            columnId: column.id,
            type: field.type,
            name: (() => {
              const base = slugify(field.name);
              let candidate = base;
              let index = 2;
              while (usedNames.has(candidate)) {
                candidate = `${base}_${index}`;
                index += 1;
              }
              usedNames.add(candidate);
              return candidate;
            })(),
            label: field.label.trim() || field.name,
            configJson: JSON.stringify({
              placeholder: field.placeholder ?? '',
              required: field.required ?? false,
              options: optionsFromText(field.optionsText),
              min: optionalNumber(field.min),
              max: optionalNumber(field.max),
              min_length: optionalNumber(field.minLength),
              max_length: optionalNumber(field.maxLength),
              pattern: field.type === 'DOCUMENT_ID' ? documentPattern(field.documentAppearance, field.pattern) : field.pattern?.trim() || undefined,
              document_appearance: field.type === 'DOCUMENT_ID' ? field.documentAppearance ?? 'alphanumeric' : undefined,
              relevant: field.relevantField ? {
                field: slugify(field.relevantField),
                operator: field.relevantOperator ?? 'equals',
                value: field.relevantValue ?? '',
              } : undefined,
              visual: field.mediaType && field.mediaType !== 'none' ? {
                type: field.mediaType,
                value: field.mediaValue ?? '',
                position: field.mediaPosition ?? 'before',
                size: field.mediaSize ?? 'medium',
              } : undefined,
            }),
            sortOrder,
          });
          sortOrder += 1;
        }
      }
      const url = `/runtime/${template.id}`;
      setRuntimeUrl(url);
      setMessage(`Plantilla guardada: ${template.name}. Ya puedes abrir Runtime.`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible guardar la plantilla.');
    } finally {
      setSaving(false);
    }
  }

  async function createMvpTemplate() {
    if (!projectId) {
      setMessage('Falta proyecto activo en la sesion.');
      return;
    }
    const template = await createDefaultCharacterizationTemplate(projectId);
    const url = `/runtime/${template.id}`;
    setRuntimeUrl(url);
    setMessage(`Plantilla creada: ${template.id}`);
  }

  return (
    <AppShell title="Constructor de Formularios">
      <div className="builder-layout">
        <aside className="builder-sidebar-stack">
          <div className="builder-connect-panel">
            <div className="builder-panel-title">
              <strong>Formulario</strong>
              <p>Configura el nombre, tema visual y grupos antes de agregar preguntas.</p>
            </div>
            <label>Nombre de la plantilla<input value={templateName} onChange={(event) => setTemplateName(event.target.value)} /></label>
            <label>Descripcion<input value={templateDescription} onChange={(event) => setTemplateDescription(event.target.value)} /></label>
            <details className="builder-theme-panel">
              <summary>Tema visual</summary>
              <div className="builder-theme-grid">
                <label>Color principal<span className="builder-color-control"><input type="color" value={theme.primaryColor} onChange={(event) => setTheme({ ...theme, primaryColor: event.target.value })} /><code>{theme.primaryColor}</code></span></label>
                <label>Color acento<span className="builder-color-control"><input type="color" value={theme.accentColor} onChange={(event) => setTheme({ ...theme, accentColor: event.target.value })} /><code>{theme.accentColor}</code></span></label>
                <label>Fondo<span className="builder-color-control"><input type="color" value={theme.backgroundColor} onChange={(event) => setTheme({ ...theme, backgroundColor: event.target.value })} /><code>{theme.backgroundColor}</code></span></label>
                <label>Bordes
                  <select value={theme.radius} onChange={(event) => setTheme({ ...theme, radius: event.target.value })}>
                    <option value="6px">Recto</option>
                    <option value="14px">Suave</option>
                    <option value="22px">Redondeado</option>
                  </select>
                </label>
              </div>
            </details>
            <button type="button" className="secondary" onClick={resetTemplate}>Nueva plantilla en blanco</button>
            <button onClick={createMvpTemplate}>Crear plantilla de caracterizacion</button>
          </div>

          <div className="builder-structure-panel">
            <div className="builder-panel-title">
              <strong>Grupos y secciones</strong>
              <p>Similar a Kobo/LimeSurvey: divide el formulario por bloques de captura.</p>
            </div>
            <div className="builder-structure-list">
              {sections.map((section, index) => (
                <button key={section.id} type="button" className={section.id === activeSectionId ? 'active' : ''} onClick={() => setActiveSectionId(section.id)}>
                  <span>{index + 1}</span>
                  <strong>{section.title || `Grupo ${index + 1}`}</strong>
                  <small>{section.fields.length} pregunta(s)</small>
                </button>
              ))}
            </div>
            <div className="builder-group-panel">
              <label>Agregar preguntas en
                <select value={activeSectionId} onChange={(event) => setActiveSectionId(event.target.value)}>
                  {sections.map((section) => <option key={section.id} value={section.id}>{section.title}</option>)}
                </select>
              </label>
              <button type="button" className="secondary" onClick={addSection}>Agregar grupo</button>
            </div>
            {message ? <span>{message}</span> : null}
            {runtimeUrl ? <a href={runtimeUrl}>Abrir Runtime</a> : null}
          </div>
        </aside>
        <BuilderCanvas
          sections={sections}
          theme={theme}
          availableFields={sections.flatMap((section) => section.fields)}
          activeSectionId={activeSectionId}
          onActiveSectionChange={setActiveSectionId}
          onSectionTitleChange={updateSection}
          onRemoveSection={removeSection}
          onFieldChange={updateField}
          onRemoveField={removeField}
          onMoveField={moveField}
          onPreview={() => setMessage('La vista previa esta debajo: edita las preguntas antes de guardar.')}
          onSave={saveTemplate}
          saving={saving}
        />
        <BuilderPalette onAddField={addField} />
      </div>
    </AppShell>
  );
}
