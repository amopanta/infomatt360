import type { ReportProjectSummary } from './api';

export type Aggregation = 'count' | 'sum' | 'average' | 'min' | 'max';

export type KpiSource =
  | { kind: 'records_total' }
  | { kind: 'status_count'; status: string }
  | { kind: 'template_count'; template_id: string }
  | { kind: 'custom_metric'; template_id: string; field_name: string; aggregation: Aggregation };

export type ChartSource =
  | { kind: 'status_breakdown' }
  | { kind: 'template_totals' }
  | { kind: 'custom_metric_by_status'; template_id: string; field_name: string; aggregation: Aggregation };

export type KpiWidget = { type: 'kpi'; title: string; source: KpiSource };
export type TableWidget = { type: 'table'; title: string };
export type ChartWidget = { type: 'chart'; title: string; chart_kind: 'bar' | 'pie'; source: ChartSource };
export type ReportWidget = KpiWidget | TableWidget | ChartWidget;

export type ChartPoint = { label: string; value: number };
export type ResolvedWidget =
  | { kind: 'kpi'; value: number; display: string }
  | { kind: 'chart'; points: ChartPoint[] }
  | { kind: 'table' };

export type ReportBoard = {
  project_id: string;
  widgets: ReportWidget[];
  summary: ReportProjectSummary;
  resolved: ResolvedWidget[];
  generated_at: string;
};

/** Mismo catalogo que backend/app/services/report_service.py::NUMERIC_AGGREGATABLE_TYPES
 * -- duplicado igual que ya se duplica el catalogo de tipos de campo entre
 * frontend y backend (ver frontend/src/modules/builder/fieldCatalog.ts). */
export const NUMERIC_AGGREGATABLE_TYPES = new Set([
  'NUMBER', 'INTEGER', 'DECIMAL', 'PERCENTAGE', 'CURRENCY', 'RANGE', 'NPS', 'RATING', 'LIKERT_5', 'LIKERT_7',
]);
