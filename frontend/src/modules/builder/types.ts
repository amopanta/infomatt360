/**
 * Proyecto: InfoMatt360
 * Modulo: Builder Types
 * Responsabilidad: Tipar el estado inicial del constructor visual web.
 */

export type BuilderPaletteItem = {
  category: string;
  type: string;
  label: string;
  description: string;
};

export type BuilderPreviewField = {
  id: string;
  type: string;
  name: string;
  label: string;
  placeholder?: string;
  required?: boolean;
  optionsText?: string;
  min?: string;
  max?: string;
  step?: string;
  minLength?: string;
  maxLength?: string;
  pattern?: string;
  documentAppearance?: 'numeric' | 'alphanumeric' | 'passport' | 'tax_id' | 'custom';
  relevantField?: string;
  relevantOperator?: 'equals' | 'not_equals' | 'not_empty' | 'empty';
  relevantValue?: string;
  mediaType?: 'none' | 'emoji' | 'image';
  mediaValue?: string;
  mediaPosition?: 'before' | 'after';
  mediaSize?: 'small' | 'medium' | 'large';
  /** LINKED_SUBFORM (ver docs/97): plantilla hija cuyas filas se capturan como registros propios. */
  childTemplateId?: string;
  /** PARENT_CHILD (ver docs/97): plantilla y campo de esa plantilla que se usan para el selector de enlace. */
  linkedTemplateId?: string;
  labelField?: string;
};

export type BuilderPreviewSection = {
  id: string;
  title: string;
  fields: BuilderPreviewField[];
};
