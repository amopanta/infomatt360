import { useEffect, useState } from 'react';
import { fetchTemplateFields } from '../acta/api';
import type { ActaFieldOption } from '../acta/types';
import { fetchProjectTemplates } from '../records/api';
import type { TemplateSummary } from '../records/api';
import { fetchTemplateFieldTypes } from './api';
import { reorderWidgets } from './widgetOrder';
import { NUMERIC_AGGREGATABLE_TYPES } from './types';
import type { Aggregation, ChartSource, ChartWidget, KpiSource, KpiWidget, ReportWidget, TableWidget } from './types';

type Props = {
  projectId: string;
  widgets: ReportWidget[];
  saving: boolean;
  onChange: (widgets: ReportWidget[]) => void;
  onSave: () => void;
  onCancel: () => void;
};

const AGGREGATIONS: Array<{ value: Aggregation; label: string }> = [
  { value: 'count', label: 'Conteo' },
  { value: 'sum', label: 'Suma' },
  { value: 'average', label: 'Promedio' },
  { value: 'min', label: 'Minimo' },
  { value: 'max', label: 'Maximo' },
];

export function ReportBoardEditor({ projectId, widgets, saving, onChange, onSave, onCancel }: Props) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<number | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);

  useEffect(() => {
    if (!projectId) return;
    fetchProjectTemplates(projectId).then(setTemplates).catch(() => setTemplates([]));
  }, [projectId]);

  function addWidget(widget: ReportWidget) {
    onChange([...widgets, widget]);
  }

  function updateWidget(index: number, widget: ReportWidget) {
    onChange(widgets.map((item, itemIndex) => (itemIndex === index ? widget : item)));
  }

  function removeWidget(index: number) {
    onChange(widgets.filter((_, itemIndex) => itemIndex !== index));
  }

  function reorder(fromIndex: number, toIndex: number) {
    onChange(reorderWidgets(widgets, fromIndex, toIndex));
  }

  return (
    <div className="reports-editor">
      <aside className="reports-palette">
        <h3>Bloques disponibles</h3>
        <p className="builder-help">Haz clic en un bloque para agregarlo al final del tablero.</p>
        <button type="button" className="reports-palette-item" onClick={() => addWidget({ type: 'kpi', title: 'Nuevo KPI', source: { kind: 'records_total' } })}>
          <strong>KPI</strong>
          <span>Una sola cifra destacada.</span>
        </button>
        <button type="button" className="reports-palette-item" onClick={() => addWidget({ type: 'table', title: 'Resumen por formulario' } satisfies TableWidget)}>
          <strong>Tabla</strong>
          <span>Resumen por formulario (mismo detalle de siempre).</span>
        </button>
        <button type="button" className="reports-palette-item" onClick={() => addWidget({ type: 'chart', title: 'Nuevo grafico', chart_kind: 'bar', source: { kind: 'status_breakdown' } })}>
          <strong>Grafico</strong>
          <span>Barra o torta sobre una metrica.</span>
        </button>
      </aside>

      <section className="reports-editor-canvas">
        {widgets.length === 0 ? (
          <div className="acta-canvas-empty">
            <h3>Este tablero aun no tiene bloques</h3>
            <p>Haz clic en un bloque de la paleta para empezar.</p>
          </div>
        ) : null}
        {widgets.map((widget, index) => (
          <div
            key={index}
            className={`reports-widget-card ${dropTarget === index ? 'drag-target' : ''}`}
            onDragOver={(event) => {
              if (draggedIndex === null) return;
              event.preventDefault();
              setDropTarget(index);
            }}
            onDragLeave={() => setDropTarget(null)}
            onDrop={(event) => {
              event.preventDefault();
              if (draggedIndex !== null) reorder(draggedIndex, index);
              setDraggedIndex(null);
              setDropTarget(null);
            }}
          >
            <div className="acta-block-header">
              <span
                className="builder-drag-handle"
                title="Arrastra para cambiar el orden"
                draggable
                onDragStart={(event) => {
                  event.dataTransfer.effectAllowed = 'move';
                  event.dataTransfer.setData('text/plain', String(index));
                  setDraggedIndex(index);
                }}
                onDragEnd={() => {
                  setDraggedIndex(null);
                  setDropTarget(null);
                }}
              >
                ⋮⋮
              </span>
              <strong>{widget.type === 'kpi' ? 'KPI' : widget.type === 'table' ? 'Tabla' : 'Gráfico'}</strong>
              <button type="button" className="secondary" onClick={() => removeWidget(index)}>Eliminar</button>
            </div>

            <label>
              <span>Título</span>
              <input value={widget.title} onChange={(event) => updateWidget(index, { ...widget, title: event.target.value })} />
            </label>

            {widget.type === 'kpi' ? (
              <KpiSourceEditor templates={templates} source={widget.source} onChange={(source) => updateWidget(index, { ...widget, source })} />
            ) : null}

            {widget.type === 'chart' ? (
              <>
                <label>
                  <span>Tipo de gráfico</span>
                  <select value={widget.chart_kind} onChange={(event) => updateWidget(index, { ...widget, chart_kind: event.target.value as ChartWidget['chart_kind'] })}>
                    <option value="bar">Barras</option>
                    <option value="pie">Torta</option>
                  </select>
                </label>
                <ChartSourceEditor templates={templates} source={widget.source} onChange={(source) => updateWidget(index, { ...widget, source })} />
              </>
            ) : null}
          </div>
        ))}
      </section>

      <div className="reports-editor-actions">
        <button type="button" className="primary" onClick={onSave} disabled={saving}>{saving ? 'Guardando...' : 'Guardar tablero'}</button>
        <button type="button" className="secondary" onClick={onCancel}>Cancelar</button>
      </div>
    </div>
  );
}

function KpiSourceEditor({ templates, source, onChange }: { templates: TemplateSummary[]; source: KpiSource; onChange: (source: KpiSource) => void }) {
  return (
    <div className="reports-source-config">
      <label>
        <span>Fuente</span>
        <select
          value={source.kind}
          onChange={(event) => {
            const kind = event.target.value as KpiSource['kind'];
            if (kind === 'records_total') onChange({ kind });
            else if (kind === 'status_count') onChange({ kind, status: '' });
            else if (kind === 'template_count') onChange({ kind, template_id: templates[0]?.id ?? '' });
            else onChange({ kind: 'custom_metric', template_id: templates[0]?.id ?? '', field_name: '', aggregation: 'count' });
          }}
        >
          <option value="records_total">Total de registros</option>
          <option value="status_count">Registros por estado</option>
          <option value="template_count">Registros de un formulario</option>
          <option value="custom_metric">Métrica personalizada (campo + agregación)</option>
        </select>
      </label>
      {source.kind === 'status_count' ? (
        <label>
          <span>Estado</span>
          <input value={source.status} onChange={(event) => onChange({ ...source, status: event.target.value })} placeholder="ej. submitted" />
        </label>
      ) : null}
      {source.kind === 'template_count' ? (
        <TemplateSelect templates={templates} value={source.template_id} onChange={(template_id) => onChange({ ...source, template_id })} />
      ) : null}
      {source.kind === 'custom_metric' ? (
        <CustomMetricFields templates={templates} templateId={source.template_id} fieldName={source.field_name} aggregation={source.aggregation} onChange={(patch) => onChange({ ...source, ...patch })} />
      ) : null}
    </div>
  );
}

function ChartSourceEditor({ templates, source, onChange }: { templates: TemplateSummary[]; source: ChartSource; onChange: (source: ChartSource) => void }) {
  return (
    <div className="reports-source-config">
      <label>
        <span>Fuente</span>
        <select
          value={source.kind}
          onChange={(event) => {
            const kind = event.target.value as ChartSource['kind'];
            if (kind === 'status_breakdown' || kind === 'template_totals') onChange({ kind });
            else onChange({ kind: 'custom_metric_by_status', template_id: templates[0]?.id ?? '', field_name: '', aggregation: 'count' });
          }}
        >
          <option value="status_breakdown">Registros por estado</option>
          <option value="template_totals">Registros por formulario</option>
          <option value="custom_metric_by_status">Métrica personalizada por estado</option>
        </select>
      </label>
      {source.kind === 'custom_metric_by_status' ? (
        <CustomMetricFields templates={templates} templateId={source.template_id} fieldName={source.field_name} aggregation={source.aggregation} onChange={(patch) => onChange({ ...source, ...patch })} />
      ) : null}
    </div>
  );
}

function TemplateSelect({ templates, value, onChange }: { templates: TemplateSummary[]; value: string; onChange: (templateId: string) => void }) {
  return (
    <label>
      <span>Formulario</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">Selecciona un formulario</option>
        {templates.map((template) => <option key={template.id} value={template.id}>{template.name}</option>)}
      </select>
    </label>
  );
}

function CustomMetricFields({
  templates,
  templateId,
  fieldName,
  aggregation,
  onChange,
}: {
  templates: TemplateSummary[];
  templateId: string;
  fieldName: string;
  aggregation: Aggregation;
  onChange: (patch: { template_id?: string; field_name?: string; aggregation?: Aggregation }) => void;
}) {
  const [fields, setFields] = useState<ActaFieldOption[]>([]);
  const [fieldTypes, setFieldTypes] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!templateId) {
      setFields([]);
      setFieldTypes({});
      return;
    }
    fetchTemplateFields(templateId).then(setFields).catch(() => setFields([]));
    fetchTemplateFieldTypes(templateId).then(setFieldTypes).catch(() => setFieldTypes({}));
  }, [templateId]);

  const selectedIsNumeric = fieldTypes[fieldName] ? NUMERIC_AGGREGATABLE_TYPES.has(fieldTypes[fieldName]) : true;

  return (
    <>
      <TemplateSelect templates={templates} value={templateId} onChange={(template_id) => onChange({ template_id, field_name: '' })} />
      <label>
        <span>Campo</span>
        <select value={fieldName} onChange={(event) => onChange({ field_name: event.target.value })} disabled={fields.length === 0}>
          <option value="">Selecciona un campo</option>
          {fields.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}
        </select>
      </label>
      <label>
        <span>Agregación</span>
        <select value={aggregation} onChange={(event) => onChange({ aggregation: event.target.value as Aggregation })}>
          {AGGREGATIONS.map((item) => (
            <option key={item.value} value={item.value} disabled={item.value !== 'count' && !selectedIsNumeric}>{item.label}</option>
          ))}
        </select>
      </label>
      {!selectedIsNumeric && aggregation !== 'count' ? <p className="reports-field-warning">Este campo no es numérico; solo admite "Conteo".</p> : null}
    </>
  );
}
