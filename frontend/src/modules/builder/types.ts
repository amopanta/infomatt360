/**
 * Proyecto: InfoMatt360
 * Modulo: Builder Types
 * Responsabilidad: Tipar el estado inicial del constructor visual web.
 */

export type BuilderPaletteItem = {
  type: string;
  label: string;
  description: string;
};

export type BuilderPreviewField = {
  id: string;
  type: string;
  label: string;
  placeholder?: string;
};

export type BuilderPreviewSection = {
  id: string;
  title: string;
  fields: BuilderPreviewField[];
};
