import type { RuntimeScalarValue } from './types';

export type RuntimeOption = {
  label: string;
  value: string;
};

export type RuntimeFieldConfig = {
  count?: number;
  count_field?: string;
  options?: unknown[];
  choices?: unknown[];
  placeholder?: string;
  required?: boolean;
  min?: number;
  max?: number;
  min_length?: number;
  max_length?: number;
  pattern?: string;
  document_appearance?: 'numeric' | 'alphanumeric' | 'passport' | 'tax_id' | 'custom';
  relevant?: {
    field?: string;
    operator?: 'equals' | 'not_equals' | 'not_empty' | 'empty';
    value?: string;
  };
  visual?: {
    type?: 'emoji' | 'image';
    value?: string;
    position?: 'before' | 'after';
    size?: 'small' | 'medium' | 'large';
  };
};

export function parseFieldConfig(configJson?: string | null): RuntimeFieldConfig {
  if (!configJson) return {};

  try {
    const parsed: unknown = JSON.parse(configJson);
    return typeof parsed === 'object' && parsed !== null && !Array.isArray(parsed)
      ? parsed as RuntimeFieldConfig
      : {};
  } catch {
    return {};
  }
}

export function normalizeOptions(config: RuntimeFieldConfig): RuntimeOption[] {
  const source = config.options ?? config.choices ?? [];

  return source.flatMap((item): RuntimeOption[] => {
    if (typeof item === 'string' || typeof item === 'number' || typeof item === 'boolean') {
      const value = String(item);
      return [{ label: value, value }];
    }

    if (typeof item !== 'object' || item === null || Array.isArray(item)) return [];

    const option = item as Record<string, unknown>;
    const rawValue = option.value ?? option.id ?? option.code;
    if (rawValue === undefined || rawValue === null) return [];

    const value = String(rawValue);
    const rawLabel = option.label ?? option.name ?? option.text ?? rawValue;
    return [{ label: String(rawLabel), value }];
  });
}

export function parseNumberInput(rawValue: string): RuntimeScalarValue {
  if (rawValue.trim() === '') return null;
  const parsed = Number(rawValue);
  return Number.isFinite(parsed) ? parsed : null;
}
