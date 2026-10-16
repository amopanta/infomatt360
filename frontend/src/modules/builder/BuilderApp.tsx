import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { BuilderCanvas } from './BuilderCanvas';
import { BuilderPalette } from './BuilderPalette';
import type { BuilderPaletteItem, BuilderPreviewField, BuilderPreviewSection } from './types';
import { createColumn, createComponent, createPage, createRow, createSection, createTemplate, fetchTemplateDetail, updateComponentProperties, updateSectionTitle, updateTemplateProperties } from './api';
import { createDefaultCharacterizationTemplate } from './createDefaultTemplate';
import { navigateTo } from '../../routeConfig';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { fetchRuntimeTemplate } from '../runtime/api';
import type { RuntimeComponent } from '../runtime/types';
import { useI18n } from '../../i18n';

function slugify(value: string) {
  const normalized = value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
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

function makeInitialSections(title: string): BuilderPreviewSection[] {
  return [{ id: 'general', title, fields: [] }];
}

function fieldFromRuntime(component: RuntimeComponent): BuilderPreviewField {
  let config: Record<string, any> = {};
  try { config = JSON.parse(component.config_json || '{}'); } catch { /* El campo sigue siendo editable si la configuración antigua no es JSON válido. */ }
  return {
    id: component.id, type: component.type, name: component.name, label: component.label,
    placeholder: config.placeholder || '', required: Boolean(config.required),
    optionsText: Array.isArray(config.options) ? config.options.map((option: { label?: string }) => option.label || '').join('\n') : '',
    min: config.min == null ? '' : String(config.min), max: config.max == null ? '' : String(config.max),
    step: config.step == null ? '' : String(config.step), minLength: config.min_length == null ? '' : String(config.min_length),
    maxLength: config.max_length == null ? '' : String(config.max_length), pattern: config.pattern || '',
    documentAppearance: config.document_appearance || 'alphanumeric', relevantField: config.relevant?.field || '',
    relevantOperator: config.relevant?.operator || 'equals', relevantValue: config.relevant?.value || '',
    mediaType: config.visual?.type || 'none', mediaValue: config.visual?.value || '',
    mediaPosition: config.visual?.position || 'before', mediaSize: config.visual?.size || 'medium',
    childTemplateId: config.child_template_id || '', linkedTemplateId: config.linked_template_id || '', labelField: config.label_field || '',
  };
}

function fieldConfig(field: BuilderPreviewField): string {
  return JSON.stringify({
    placeholder: field.placeholder ?? '', required: field.required ?? false,
    options: optionsFromText(field.optionsText), min: optionalNumber(field.min), max: optionalNumber(field.max),
    step: field.type === 'RANGE' ? optionalNumber(field.step) : undefined,
    min_length: optionalNumber(field.minLength), max_length: optionalNumber(field.maxLength),
    pattern: field.type === 'DOCUMENT_ID' ? documentPattern(field.documentAppearance, field.pattern) : field.pattern?.trim() || undefined,
    document_appearance: field.type === 'DOCUMENT_ID' ? field.documentAppearance ?? 'alphanumeric' : undefined,
    relevant: field.relevantField ? { field: slugify(field.relevantField), operator: field.relevantOperator ?? 'equals', value: field.relevantValue ?? '' } : undefined,
    visual: field.mediaType && field.mediaType !== 'none' ? { type: field.mediaType, value: field.mediaValue ?? '', position: field.mediaPosition ?? 'before', size: field.mediaSize ?? 'medium' } : undefined,
    child_template_id: field.type === 'LINKED_SUBFORM' ? field.childTemplateId || undefined : undefined,
    linked_template_id: field.type === 'PARENT_CHILD' ? field.linkedTemplateId || undefined : undefined,
    label_field: field.type === 'PARENT_CHILD' ? field.labelField?.trim() || undefined : undefined,
  });
}

export function BuilderApp() {
  const { t } = useI18n();
  const editingTemplateId = window.location.pathname.match(/^\/builder\/edit\/([^/]+)$/)?.[1] ?? '';
  const initialSections = makeInitialSections(t('builder.editor.generalSection'));
  const [message, setMessage] = useState('');
  const [runtimeUrl, setRuntimeUrl] = useState('');
  const [templateName, setTemplateName] = useState(t('builder.editor.newTemplateName'));
  const [templateDescription, setTemplateDescription] = useState('');
  const [theme, setTheme] = useState({ primaryColor: '#0066cc', accentColor: '#00c2ff', backgroundColor: '#ffffff', radius: '18px' });
  const [sections, setSections] = useState<BuilderPreviewSection[]>(initialSections);
  const [activeSectionId, setActiveSectionId] = useState(initialSections[0].id);
  const [saving, setSaving] = useState(false);
  const [projectTemplates, setProjectTemplates] = useState<TemplateSummary[]>([]);
  const [existingSectionIds, setExistingSectionIds] = useState<Set<string>>(new Set());
  const [existingFieldIds, setExistingFieldIds] = useState<Set<string>>(new Set());
  const [originalConfigs, setOriginalConfigs] = useState<Record<string, string | null>>({});
  const [submissionsCount, setSubmissionsCount] = useState(0);
  const [loaded, setLoaded] = useState(!editingTemplateId);
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';

  useEffect(() => {
    if (!projectId) return;
    fetchProjectTemplates(projectId).then(setProjectTemplates).catch(() => setProjectTemplates([]));
  }, [projectId]);

  useEffect(() => {
    if (!editingTemplateId) return;
    Promise.all([fetchTemplateDetail(editingTemplateId), fetchRuntimeTemplate(editingTemplateId)])
      .then(([detail, runtime]) => {
        setTemplateName(detail.name);
        setTemplateDescription(detail.description || '');
        try { if (detail.theme_json) setTheme((current) => ({ ...current, ...JSON.parse(detail.theme_json!) })); } catch { /* conservar tema predeterminado */ }
        const loadedSections = runtime.pages.flatMap((page) => page.sections.map((section) => ({
          id: section.id, title: section.title,
          fields: section.rows.flatMap((row) => row.columns.flatMap((column) => column.components.map(fieldFromRuntime))),
        })));
        setSections(loadedSections.length ? loadedSections : initialSections);
        setActiveSectionId(loadedSections[0]?.id || initialSections[0].id);
        setExistingSectionIds(new Set(loadedSections.map((section) => section.id)));
        setExistingFieldIds(new Set(loadedSections.flatMap((section) => section.fields.map((field) => field.id))));
        setOriginalConfigs(Object.fromEntries(runtime.pages.flatMap((page) => page.sections.flatMap((section) => section.rows.flatMap((row) => row.columns.flatMap((column) => column.components.map((component) => [component.id, component.config_json ?? null])))))));
        setSubmissionsCount(detail.submissions_count || 0);
        setLoaded(true);
      })
      .catch((error: Error) => setMessage(error.message));
  }, [editingTemplateId]);

  function resetTemplate() {
    const sectionId = crypto.randomUUID();
    setTemplateName(t('builder.editor.newTemplateName'));
    setTemplateDescription('');
    setTheme({ primaryColor: '#0066cc', accentColor: '#00c2ff', backgroundColor: '#ffffff', radius: '18px' });
    setSections([{ id: sectionId, title: t('builder.editor.generalSection'), fields: [] }]);
    setActiveSectionId(sectionId);
    setRuntimeUrl('');
    setMessage(t('builder.editor.newTemplateReady'));
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
      const nextSections = currentSections.length ? [...currentSections] : [{ id: 'general', title: t('builder.editor.generalSection'), fields: [] }];
      const targetIndex = Math.max(0, nextSections.findIndex((section) => section.id === activeSectionId));
      nextSections[targetIndex] = { ...nextSections[targetIndex], fields: [...nextSections[targetIndex].fields, field] };
      return nextSections;
    });
    setMessage(t('builder.editor.questionAdded', { label: item.label }));
  }

  function addSection() {
    const nextNumber = sections.length + 1;
    const section = { id: crypto.randomUUID(), title: t('builder.editor.groupDefault', { number: nextNumber }), fields: [] };
    setSections((currentSections) => [...currentSections, section]);
    setActiveSectionId(section.id);
    setMessage(t('builder.editor.groupCreated', { title: section.title }));
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
    setMessage(t('builder.editor.orderUpdated'));
  }

  async function saveTemplate() {
    if (!projectId) {
      setMessage(t('builder.editor.missingProject'));
      return;
    }
    const fields = sections.flatMap((section) => section.fields);
    if (!fields.length) {
      setMessage(t('builder.editor.addQuestionFirst'));
      return;
    }
    if (!templateName.trim()) { setMessage(t('builder.editor.enterFormName')); return; }
    setSaving(true);
    setMessage(t('builder.editor.savingTemplate'));
    try {
      if (editingTemplateId) {
        await updateTemplateProperties(editingTemplateId, { name: templateName.trim(), description: templateDescription || null, themeJson: JSON.stringify(theme) });
        const usedNames = new Set(fields.filter((field) => existingFieldIds.has(field.id)).map((field) => field.name));
        let order = 1;
        for (const sectionDraft of sections) {
          let sectionId = sectionDraft.id;
          if (existingSectionIds.has(sectionId)) {
            await updateSectionTitle(sectionId, sectionDraft.title.trim() || t('builder.editor.sectionDefault'));
          } else {
            const page = await createPage({ templateId: editingTemplateId, title: sectionDraft.title.trim() || t('builder.editor.sectionDefault'), sortOrder: order });
            const section = await createSection({ pageId: page.id, title: sectionDraft.title.trim() || t('builder.editor.sectionDefault'), sortOrder: order });
            sectionId = section.id;
          }
          for (const field of sectionDraft.fields) {
            const config = JSON.parse(fieldConfig(field));
            if (existingFieldIds.has(field.id)) {
              let original: Record<string, unknown> = {};
              try { original = JSON.parse(originalConfigs[field.id] || '{}'); } catch { /* conservar las propiedades editadas */ }
              await updateComponentProperties(field.id, { label: field.label.trim() || field.name, name: field.name.trim(), configJson: JSON.stringify({ ...original, ...config }) });
            } else {
              const row = await createRow({ sectionId, sortOrder: order });
              const column = await createColumn({ rowId: row.id, desktopWidth: 12, sortOrder: 1 });
              const base = slugify(field.name);
              let name = base;
              let suffix = 2;
              while (usedNames.has(name)) { name = `${base}_${suffix}`; suffix += 1; }
              usedNames.add(name);
              await createComponent({ templateId: editingTemplateId, columnId: column.id, type: field.type, name, label: field.label.trim() || name, configJson: JSON.stringify(config), sortOrder: order });
            }
            order += 1;
          }
        }
        setMessage(t('builder.editor.changesSaved'));
        navigateTo(`/builder/form/${editingTemplateId}`);
        return;
      }
      const template = await createTemplate({ projectId, name: templateName.trim() || t('builder.editor.newTemplateName'), description: templateDescription || undefined, status: 'draft', themeJson: JSON.stringify(theme) });
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
            configJson: fieldConfig(field),
            sortOrder,
          });
          sortOrder += 1;
        }
      }
      const url = `/runtime/${template.id}`;
      setRuntimeUrl(url);
      setMessage(t('builder.editor.draftSaved', { name: template.name }));
      navigateTo(`/builder/form/${template.id}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('builder.editor.saveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function createMvpTemplate() {
    if (!projectId) {
      setMessage(t('builder.editor.missingProject'));
      return;
    }
    const template = await createDefaultCharacterizationTemplate(projectId);
    const url = `/runtime/${template.id}`;
    setRuntimeUrl(url);
    setMessage(t('builder.editor.templateCreated', { id: template.id }));
    navigateTo(`/builder/form/${template.id}`);
  }

  return (
    <AppShell title={t('builder.editor.constructorTitle')}>
      <div className="builder-return"><a href={editingTemplateId ? `/builder/form/${editingTemplateId}` : '/builder'}>{t('builder.editor.backToForm')}</a><span>{editingTemplateId ? t('builder.editor.editingExisting', { count: submissionsCount }) : t('builder.editor.newFormsSavedAsDraft')}</span></div>
      {!loaded && <p role="status">{message || t('builder.editor.loadingExisting')}</p>}
      {loaded && <>
      <div className="builder-layout">
        <aside className="builder-sidebar-stack">
          <div className="builder-connect-panel">
            <div className="builder-panel-title">
              <strong>{t('builder.editor.formPanelTitle')}</strong>
              <p>{t('builder.editor.formPanelDesc')}</p>
            </div>
            <label>{t('builder.editor.formNameLabel')}<input value={templateName} maxLength={180} onChange={(event) => setTemplateName(event.target.value)} /></label>
            <label>{t('builder.editor.descriptionLabel')}<input value={templateDescription} onChange={(event) => setTemplateDescription(event.target.value)} /></label>
            <details className="builder-theme-panel">
              <summary>{t('builder.editor.visualTheme')}</summary>
              <div className="builder-theme-grid">
                <label>{t('builder.editor.primaryColor')}<span className="builder-color-control"><input type="color" value={theme.primaryColor} onChange={(event) => setTheme({ ...theme, primaryColor: event.target.value })} /><code>{theme.primaryColor}</code></span></label>
                <label>{t('builder.editor.accentColor')}<span className="builder-color-control"><input type="color" value={theme.accentColor} onChange={(event) => setTheme({ ...theme, accentColor: event.target.value })} /><code>{theme.accentColor}</code></span></label>
                <label>{t('builder.editor.background')}<span className="builder-color-control"><input type="color" value={theme.backgroundColor} onChange={(event) => setTheme({ ...theme, backgroundColor: event.target.value })} /><code>{theme.backgroundColor}</code></span></label>
                <label>{t('builder.editor.borders')}
                  <select value={theme.radius} onChange={(event) => setTheme({ ...theme, radius: event.target.value })}>
                    <option value="6px">{t('builder.editor.borderStraight')}</option>
                    <option value="14px">{t('builder.editor.borderSoft')}</option>
                    <option value="22px">{t('builder.editor.borderRounded')}</option>
                  </select>
                </label>
              </div>
            </details>
            {!editingTemplateId && <button type="button" className="secondary" onClick={resetTemplate}>{t('builder.editor.newBlankTemplate')}</button>}
            {!editingTemplateId && <button onClick={createMvpTemplate}>{t('builder.editor.createCharacterization')}</button>}
          </div>

          <div className="builder-structure-panel">
            <div className="builder-panel-title">
              <strong>{t('builder.editor.groupsAndSections')}</strong>
              <p>{t('builder.editor.groupsDesc')}</p>
            </div>
            <div className="builder-structure-list">
              {sections.map((section, index) => (
                <button key={section.id} type="button" className={section.id === activeSectionId ? 'active' : ''} onClick={() => setActiveSectionId(section.id)}>
                  <span>{index + 1}</span>
                  <strong>{section.title || t('builder.editor.groupDefault', { number: index + 1 })}</strong>
                  <small>{t('builder.editor.questionCount', { count: section.fields.length })}</small>
                </button>
              ))}
            </div>
            <div className="builder-group-panel">
              <label>{t('builder.editor.addQuestionsIn')}
                <select value={activeSectionId} onChange={(event) => setActiveSectionId(event.target.value)}>
                  {sections.map((section) => <option key={section.id} value={section.id}>{section.title}</option>)}
                </select>
              </label>
              <button type="button" className="secondary" onClick={addSection}>{t('builder.editor.addGroup')}</button>
            </div>
            {message ? <span>{message}</span> : null}
            {runtimeUrl ? <a href={runtimeUrl}>{t('builder.editor.openRuntime')}</a> : null}
          </div>
        </aside>
        <BuilderCanvas
          sections={sections}
          theme={theme}
          availableFields={sections.flatMap((section) => section.fields)}
          projectTemplates={projectTemplates}
          activeSectionId={activeSectionId}
          onActiveSectionChange={setActiveSectionId}
          onSectionTitleChange={updateSection}
          onRemoveSection={removeSection}
          onFieldChange={updateField}
          onRemoveField={removeField}
          onMoveField={moveField}
          onPreview={() => setMessage(t('builder.editor.previewHint'))}
          onSave={saveTemplate}
          saving={saving}
          lockedFieldIds={existingFieldIds}
          lockedSectionIds={existingSectionIds}
          lockTechnicalNames={submissionsCount > 0}
          disableReorder={Boolean(editingTemplateId)}
        />
        <BuilderPalette onAddField={addField} />
      </div>
      </>}
    </AppShell>
  );
}
