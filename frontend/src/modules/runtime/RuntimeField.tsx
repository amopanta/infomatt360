import type { RuntimeComponent, RuntimeFormValues } from './types';

type Props = {
  component: RuntimeComponent;
  values: RuntimeFormValues;
  onChange: (fieldName: string, value: string | number | boolean | null) => void;
};

export function RuntimeField(props: Props) {
  const { component, values, onChange } = props;
  const value = values[component.name] ?? '';
  const type = component.type.toUpperCase();

  if (type === 'TEXTAREA') {
    return <textarea aria-label={component.label} value={String(value)} onChange={(e) => onChange(component.name, e.target.value)} />;
  }

  return <input aria-label={component.label} value={String(value)} onChange={(e) => onChange(component.name, e.target.value)} />;
}
