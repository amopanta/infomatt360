export type ActaLogoBlock = { type: 'logo'; alignment: 'left' | 'center' | 'right' };
export type ActaHeaderBlock = { type: 'header'; text: string; level: 1 | 2 | 3 };
export type ActaTableBlock = { type: 'table'; field_names: string[] };
export type ActaSignatureBlock = { type: 'signature'; label: string };

export type ActaBlock = ActaLogoBlock | ActaHeaderBlock | ActaTableBlock | ActaSignatureBlock;

export type ActaLayout = { blocks: ActaBlock[] };

/** Fila de `ActaTemplate`, legado o constructor visual (ver docs/109) --
 * `layout_json`/`template_id` solo estan presentes en plantillas del
 * constructor visual. */
export type ActaTemplateSummary = {
  id: string;
  project_id: string;
  name: string;
  html_template?: string | null;
  layout_json?: string | null;
  template_id?: string | null;
  created_at: string;
  updated_at: string;
};

export type ActaFieldOption = { name: string; label: string };
