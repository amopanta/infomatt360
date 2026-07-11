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
};

export type BuilderPreviewSection = {
  id: string;
  title: string;
  fields: BuilderPreviewField[];
};
