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

type Props = { mode: 'create' } | { mode: 'edit'; actaTemplateId: string };

export function ActaBuilderApp(props: Props) {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [name, setName] = useState('Nueva acta');
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
          setMessage('Plantilla de acta no encontrada.');
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
      setMessage('Selecciona un formulario para esta acta.');
      return;
    }
    if (blocks.length === 0) {
      setMessage('Agrega al menos un bloque antes de guardar.');
      return;
    }
    setSaving(true);
    setMessage('Guardando plantilla...');
    try {
      const payload = { project_id: projectId, name: name.trim() || 'Nueva acta', template_id: formTemplateId, layout: { blocks } };
      const saved = actaTemplateId ? await updateActaLayoutTemplate(actaTemplateId, payload) : await createActaLayoutTemplate(payload);
      setActaTemplateId(saved.id);
      setMessage('Plantilla guardada.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible guardar la plantilla.');
    } finally {
      setSaving(false);
    }
  }

  async function generatePreview() {
    if (!actaTemplateId) {
      setMessage('Guarda la plantilla antes de generar un PDF de prueba.');
      return;
    }
    if (!previewRecordId) {
      setMessage('Selecciona un registro para generar el PDF.');
      return;
    }
    setGenerating(true);
    setMessage('');
    try {
      await renderActaFromRecord(actaTemplateId, previewRecordId, name.trim() || 'acta');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible generar el PDF.');
    } finally {
      setGenerating(false);
    }
  }

  if (legacyBlocked) {
    return (
      <AppShell title="Actas">
        <main className="acta-shell">
          <p role="status">Esta plantilla usa el camino legado (HTML crudo) y no se puede editar con el constructor visual.</p>
          <a href="/acta">Volver a la lista de plantillas</a>
        </main>
      </AppShell>
    );
  }

  return (
    <AppShell title="Actas">
      <main className="acta-shell acta-builder-shell">
        <header className="acta-builder-header">
          <label>
            <span>Nombre de la plantilla</span>
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            <span>Formulario para el que se genera</span>
            <select value={formTemplateId} onChange={(event) => setFormTemplateId(event.target.value)} disabled={Boolean(actaTemplateId)}>
              <option value="">Selecciona un formulario</option>
              {projectTemplates.map((template) => (
                <option key={template.id} value={template.id}>{template.name}</option>
              ))}
            </select>
          </label>
          <div className="acta-builder-actions">
            <button type="button" className="primary" onClick={() => void saveTemplate()} disabled={saving}>
              {saving ? 'Guardando...' : 'Guardar plantilla'}
            </button>
          </div>
        </header>
        {message ? <p role="status">{message}</p> : null}

        <div className="acta-builder-body">
          <ActaPalette onAddBlock={addBlock} />
          <ActaCanvas blocks={blocks} fields={fields} onReorder={reorder} onUpdateBlock={updateBlock} onRemoveBlock={removeBlock} />
        </div>

        <section className="acta-preview-panel">
          <h3>Generar PDF de prueba</h3>
          <p>Sirve de vista previa real y, a la vez, es el mismo flujo de producción disponible desde Registros.</p>
          <div className="acta-preview-controls">
            <select value={previewRecordId} onChange={(event) => setPreviewRecordId(event.target.value)} disabled={previewRecords.length === 0}>
              <option value="">Selecciona un registro</option>
              {previewRecords.map((record) => (
                <option key={record.id} value={record.id}>{new Date(record.created_at).toLocaleString()} · {record.id.slice(0, 8)}</option>
              ))}
            </select>
            <button type="button" onClick={() => void generatePreview()} disabled={generating}>
              {generating ? 'Generando...' : 'Generar PDF de prueba'}
            </button>
          </div>
        </section>
      </main>
    </AppShell>
  );
}
