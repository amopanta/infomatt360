import { useEffect, useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import { fetchProjectTemplates, fetchTemplateRecords } from '../records/api';
import type { RuntimeRecord, TemplateSummary } from '../records/api';
import { ActaCanvas } from './ActaCanvas';
import { ActaPalette } from './ActaPalette';
import { createActaLayoutTemplate, fetchActaTemplates, fetchTemplateFields, renderActaFromRecord, updateActaLayoutTemplate } from './api';
import type { ActaBlock, ActaFieldOption } from './types';
import { reorderBlocks } from './blockOrder';
import { useI18n } from '../../i18n';

type Props = { mode: 'create' } | { mode: 'edit'; actaTemplateId: string };

export function ActaBuilderApp(props: Props) {
  const { t } = useI18n();
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [name, setName] = useState(t('acta.newActa'));
  const [formTemplateId, setFormTemplateId] = useState('');
  const [projectTemplates, setProjectTemplates] = useState<TemplateSummary[]>([]);
  const [fields, setFields] = useState<ActaFieldOption[]>([]);
  const [blocks, setBlocks] = useState<ActaBlock[]>([]);
  const [actaTemplateId, setActaTemplateId] = useState<string | null>(props.mode === 'edit' ? props.actaTemplateId : null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [legacyBlocked, setLegacyBlocked] = useState(false);

  const [previewRecords, setPreviewRecords] = useState<RuntimeRecord[]>([]);
  const [previewRecordId, setPreviewRecordId] = useState('');
  const [generating, setGenerating] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    fetchProjectTemplates(projectId).then(setProjectTemplates).catch(() => setProjectTemplates([]));
  }, [projectId]);

  useEffect(() => {
    if (props.mode !== 'edit' || !projectId) return;
    fetchActaTemplates(projectId)
      .then((templates) => {
        const existing = templates.find((template) => template.id === props.actaTemplateId);
        if (!existing) {
          setMessage(t('acta.templateNotFound'));
          return;
        }
        if (!existing.layout_json || !existing.template_id) {
          setLegacyBlocked(true);
          return;
        }
        setName(existing.name);
        setFormTemplateId(existing.template_id);
        setBlocks(JSON.parse(existing.layout_json).blocks ?? []);
      })
      .catch((error: Error) => setMessage(error.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId, props.mode]);

  useEffect(() => {
    if (!formTemplateId) {
      setFields([]);
      setPreviewRecords([]);
      return;
    }
    fetchTemplateFields(formTemplateId).then(setFields).catch(() => setFields([]));
    fetchTemplateRecords(formTemplateId).then(setPreviewRecords).catch(() => setPreviewRecords([]));
  }, [formTemplateId]);

  function addBlock(block: ActaBlock) {
    setBlocks((current) => [...current, block]);
  }

  function updateBlock(index: number, block: ActaBlock) {
    setBlocks((current) => current.map((item, itemIndex) => (itemIndex === index ? block : item)));
  }

  function removeBlock(index: number) {
    setBlocks((current) => current.filter((_, itemIndex) => itemIndex !== index));
  }

  function reorder(fromIndex: number, toIndex: number) {
    setBlocks((current) => reorderBlocks(current, fromIndex, toIndex));
  }

  async function saveTemplate() {
    if (!projectId || !formTemplateId) {
      setMessage(t('acta.selectFormForActa'));
      return;
    }
    if (blocks.length === 0) {
      setMessage(t('acta.addBlockFirst'));
      return;
    }
    setSaving(true);
    setMessage(t('acta.savingTemplateMsg'));
    try {
      const payload = { project_id: projectId, name: name.trim() || t('acta.newActa'), template_id: formTemplateId, layout: { blocks } };
      const saved = actaTemplateId ? await updateActaLayoutTemplate(actaTemplateId, payload) : await createActaLayoutTemplate(payload);
      setActaTemplateId(saved.id);
      setMessage(t('acta.templateSaved'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('acta.templateSaveFailed'));
    } finally {
      setSaving(false);
    }
  }

  async function generatePreview() {
    if (!actaTemplateId) {
      setMessage(t('acta.saveBeforeGenerate'));
      return;
    }
    if (!previewRecordId) {
      setMessage(t('acta.selectRecordForPdf'));
      return;
    }
    setGenerating(true);
    setMessage('');
    try {
      await renderActaFromRecord(actaTemplateId, previewRecordId, name.trim() || 'acta');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('acta.pdfGenerateFailed'));
    } finally {
      setGenerating(false);
    }
  }

  if (legacyBlocked) {
    return (
      <AppShell title={t('acta.title')}>
        <main className="acta-shell">
          <p role="status">{t('acta.legacyBlocked')}</p>
          <a href="/acta">{t('acta.backToList')}</a>
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell title={t('acta.title')}>
      <main className="acta-shell acta-builder-shell">
        <header className="acta-builder-header">
          <label>
            <span>{t('acta.templateName')}</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            <span>{t('acta.formTarget')}</span>
            <select value={formTemplateId} onChange={(event) => setFormTemplateId(event.target.value)} disabled={Boolean(actaTemplateId)}>
              <option value="">{t('acta.selectForm')}</option>
              {projectTemplates.map((template) => (
                <option key={template.id} value={template.id}>{template.name}</option>
              ))}
            </select>
          </label>
          <div className="acta-builder-actions">
            <button type="button" className="primary" onClick={() => void saveTemplate()} disabled={saving}>
              {saving ? t('acta.savingTemplate') : t('acta.saveTemplate')}
            </button>
          </div>
        </header>
        {message ? <p role="status">{message}</p> : null}

        <div className="acta-builder-body">
          <ActaPalette onAddBlock={addBlock} />
          <ActaCanvas blocks={blocks} fields={fields} onReorder={reorder} onUpdateBlock={updateBlock} onRemoveBlock={removeBlock} />
        </div>

        <section className="acta-preview-panel">
          <h3>{t('acta.generateTestPdf')}</h3>
          <p>{t('acta.testPdfDescription')}</p>
          <div className="acta-preview-controls">
            <select value={previewRecordId} onChange={(event) => setPreviewRecordId(event.target.value)} disabled={previewRecords.length === 0}>
              <option value="">{t('acta.selectRecord')}</option>
              {previewRecords.map((record) => (
                <option key={record.id} value={record.id}>{new Date(record.created_at).toLocaleString()} · {record.id.slice(0, 8)}</option>
              ))}
            </select>
            <button type="button" onClick={() => void generatePreview()} disabled={generating}>
              {generating ? t('acta.generating') : t('acta.generateTestPdfButton')}
            </button>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
