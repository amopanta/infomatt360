/**
 * Proyecto: InfoMatt360
 * Modulo: Runtime Types
 * Responsabilidad: Tipar el JSON entregado por el backend Runtime.
 * Notas: Estos tipos deben mantenerse alineados con backend/app/schemas/runtime.py.
 */

export type RuntimeComponent = {
  id: string;
  type: string;
  name: string;
  label: string;
  config_json?: string | null;
  rules_json?: string | null;
};

export type RuntimeColumn = {
  id: string;
  desktop_width: number;
  tablet_width: number;
  mobile_width: number;
  components: RuntimeComponent[];
};

export type RuntimeRow = {
  id: string;
  columns: RuntimeColumn[];
};

export type RuntimeSection = {
  id: string;
  title: string;
  description?: string | null;
  rows: RuntimeRow[];
};

export type RuntimePage = {
  id: string;
  title: string;
  description?: string | null;
  sections: RuntimeSection[];
};

export type RuntimeTemplate = {
  template_id: string;
  name: string;
  status: string;
  theme_json?: string | null;
  pages: RuntimePage[];
};

export type RepeatItem = {
  id: string;
  index: number;
  values: Record<string, unknown>;
};

export type RuntimeScalarValue = string | number | boolean | null;
export type RuntimeFileValue = {
  file_asset_id: string;
  name: string;
  mime_type?: string | null;
  size_bytes: number;
};
export type RuntimeFormValue = RuntimeScalarValue | string[] | RepeatItem[] | RuntimeFileValue | RuntimeFileValue[] | RuntimeGeoValue;
export type RuntimeFormValues = Record<string, RuntimeFormValue>;
import type { RuntimeGeoValue } from './geoEngine';
