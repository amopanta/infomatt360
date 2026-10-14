import { useEffect, useState } from 'react';
import { useI18n } from '../../i18n';
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

export function ReportBoardEditor({ projectId, widgets, saving, onChange, onSave, onCancel }: Props) {
  const { t } = useI18n();
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<number | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);

  const AGGREGATIONS: Array<{ value: Aggregation; label: string }> = [
    { value: 'count', label: t('reports.board.aggCount') },
    { value: 'sum', label: t('reports.board.aggSum') },
    { value: 'average', label: t('reports.board.aggAverage') },
    { value: 'min', label: t('reports.board.aggMin') },
    { value: 'max', label: t('reports.board.aggMax') },
  ];

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
        <h3>{t('reports.board.availableBlocks')}</h3>
        <p className="builder-help">{t('reports.board.blockHelp')}</p>
        <button type="button" className="reports-palette-item" onClick={() => addWidget({ type: 'kpi', title: t('reports.board.newKpi'), source: { kind: 'records_total' } })}>
          <strong>{t('reports.board.kpiLabel')}</strong>
          <span>{t('reports.board.kpiDescription')}</span>
        </button>
        <button type="button" className="reports-palette-item" onClick={() => addWidget({ type: 'table', title: t('reports.board.tableSummary') } satisfies TableWidget)}>
          <strong>{t('reports.board.tableLabel')}</strong>
          <span>{t('reports.board.tableDescription')}</span>
        </button>
        <button type="button" className="reports-palette-item" onClick={() => addWidget({ type: 'chart', title: t('reports.board.newChart'), chart_kind: 'bar', source: { kind: 'status_breakdown' } })}>
          <strong>{t('reports.board.chartLabel')}</strong>
          <span>{t('reports.board.chartDescription')}</span>
        </button>
      </aside>

      <section className="reports-editor-canvas">
        {widgets.length === 0 ? (
          <div className="acta-canvas-empty">
            <h3>{t('reports.board.emptyTitle')}</h3>
            <p>{t('reports.board.emptyHint')}</p>
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
                title={t('reports.board.dragHint')}
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
              <strong>{widget.type === 'kpi' ? t('reports.board.blockKpi') : widget.type === 'table' ? t('reports.board.blockTable') : t('reports.board.blockChart')}</strong>
              <button type="button" className="secondary" onClick={() => removeWidget(index)}>{t('reports.board.deleteBlock')}</button>
            </div>

            <label>
              <span>{t('reports.board.titleLabel')}</span>
              <input value={widget.title} onChange={(event) => updateWidget(index, { ...widget, title: event.target.value })} />
            </label>

            {widget.type === 'kpi' ? (
              <KpiSourceEditor templates={templates} source={widget.source} onChange={(source) => updateWidget(index, { ...widget, source })} />
            ) : null}

            {widget.type === 'chart' ? (
              <>
                <label>
                  <span>{t('reports.board.chartKindLabel')}</span>
                  <select value={widget.chart_kind} onChange={(event) => updateWidget(index, { ...widget, chart_kind: event.target.value as ChartWidget['chart_kind'] })}>
                    <option value="bar">{t('reports.board.chartBar')}</option>
                    <option value="pie">{t('reports.board.chartPie')}</option>
                  </select>
                </label>
                <ChartSourceEditor templates={templates} source={widget.source} onChange={(source) => updateWidget(index, { ...widget, source })} />
              </>
            ) : null}
          </div>
        ))}
      </section>

      <div className="reports-editor-actions">
        <button type="button" className="primary" onClick={onSave} disabled={saving}>{saving ? t('reports.board.saving') : t('reports.board.saveBoard')}</button>
        <button type="button" className="secondary" onClick={onCancel}>{t('reports.board.cancel')}</button>
      </div>
    </div>
  );
}

function KpiSourceEditor({ templates, source, onChange }: { templates: TemplateSummary[]; source: KpiSource; onChange: (source: KpiSource) => void }) {
  const { t } = useI18n();
  return (
    <div className="reports-source-config">
      <label>
        <span>{t('reports.board.sourceLabel')}</span>
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
          <option value="records_total">{t('reports.board.sourceRecordsTotal')}</option>
          <option value="status_count">{t('reports.board.sourceStatusCount')}</option>
          <option value="template_count">{t('reports.board.sourceTemplateCount')}</option>
          <option value="custom_metric">{t('reports.board.sourceCustomMetric')}</option>
        </select>
      </label>
      {source.kind === 'status_count' ? (
        <label>
          <span>{t('reports.board.statusLabel')}</span>
          <input value={source.status} onChange={(event) => onChange({ ...source, status: event.target.value })} placeholder={t('reports.board.statusPlaceholder')} />
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
  const { t } = useI18n();
  return (
    <div className="reports-source-config">
      <label>
        <span>{t('reports.board.sourceLabel')}</span>
        <select
          value={source.kind}
          onChange={(event) => {
            const kind = event.target.value as ChartSource['kind'];
            if (kind === 'status_breakdown' || kind === 'template_totals') onChange({ kind });
            else onChange({ kind: 'custom_metric_by_status', template_id: templates[0]?.id ?? '', field_name: '', aggregation: 'count' });
          }}
        >
          <option value="status_breakdown">{t('reports.board.sourceStatusBreakdown')}</option>
          <option value="template_totals">{t('reports.board.sourceTemplateTotals')}</option>
          <option value="custom_metric_by_status">{t('reports.board.sourceCustomByStatus')}</option>
        </select>
      </label>
      {source.kind === 'custom_metric_by_status' ? (
        <CustomMetricFields templates={templates} templateId={source.template_id} fieldName={source.field_name} aggregation={source.aggregation} onChange={(patch) => onChange({ ...source, ...patch })} />
      ) : null}
    </div>
  );
}

function TemplateSelect({ templates, value, onChange }: { templates: TemplateSummary[]; value: string; onChange: (templateId: string) => void }) {
  const { t } = useI18n();
  return (
    <label>
      <span>{t('reports.board.formLabel')}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        <option value="">{t('reports.board.selectForm')}</option>
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
  const { t } = useI18n();
  const [fields, setFields] = useState<ActaFieldOption[]>([]);
  const [fieldTypes, setFieldTypes] = useState<Record<string, string>>({});

  const AGGREGATIONS: Array<{ value: Aggregation; label: string }> = [
    { value: 'count', label: t('reports.board.aggCount') },
    { value: 'sum', label: t('reports.board.aggSum') },
    { value: 'average', label: t('reports.board.aggAverage') },
    { value: 'min', label: t('reports.board.aggMin') },
    { value: 'max', label: t('reports.board.aggMax') },
  ];

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
        <span>{t('reports.board.fieldLabel')}</span>
        <select value={fieldName} onChange={(event) => onChange({ field_name: event.target.value })} disabled={fields.length === 0}>
          <option value="">{t('reports.board.selectField')}</option>
          {fields.map((field) => <option key={field.name} value={field.name}>{field.label}</option>)}
        </select>
      </label>
      <label>
        <span>{t('reports.board.aggregationLabel')}</span>
        <select value={aggregation} onChange={(event) => onChange({ aggregation: event.target.value as Aggregation })}>
          {AGGREGATIONS.map((item) => (
            <option key={item.value} value={item.value} disabled={item.value !== 'count' && !selectedIsNumeric}>{item.label}</option>
          ))}
        </select>
      </label>
      {!selectedIsNumeric && aggregation !== 'count' ? <p className="reports-field-warning">{t('reports.board.fieldNotNumeric')}</p> : null}
    </>
  );
}
