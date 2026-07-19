export type TableauColumnDataType = 'bool' | 'date' | 'datetime' | 'float' | 'int' | 'string';

export type TableauColumnDef = {
  id: string;
  alias: string;
  dataType: TableauColumnDataType;
};

export type ExternalFieldSchema = {
  id: string;
  template_id: string;
  column_id?: string | null;
  component_type: string;
  name: string;
  label: string;
  config_json?: string | null;
  rules_json?: string | null;
  sort_order?: number;
};

export type ExternalTemplateSummary = {
  id: string;
  project_id: string;
  name: string;
  description?: string | null;
  status: string;
  theme_json?: string | null;
};

export type ExternalRecordTabularRow = {
  record_id: string;
  status: string;
  submitted_by?: string | null;
  participant_id?: string | null;
  created_at: string;
  updated_at: string;
  fields: Record<string, unknown>;
};

export type ExternalRecordTabularPage = {
  template_id: string;
  columns: string[];
  items: ExternalRecordTabularRow[];
  total: number;
  limit: number;
  offset: number;
};
