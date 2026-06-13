import { RuntimeField } from './RuntimeField';
import type { RuntimeFormValues, RuntimeTemplate } from './types';

type Props = {
  template: RuntimeTemplate;
  values: RuntimeFormValues;
  onValueChange: (fieldName: string, value: string | number | boolean | null) => void;
};

function widthStyle(column: { desktop_width: number; tablet_width: number; mobile_width: number }) {
  return {
    '--desktop-span': String(column.desktop_width || 12),
    '--tablet-span': String(column.tablet_width || 12),
    '--mobile-span': String(column.mobile_width || 12),
  } as React.CSSProperties;
}

export function RuntimeRenderer({ template, values, onValueChange }: Props) {
  return (
    <main className="runtime-shell">
      <h1>{template.name}</h1>
      {template.pages.map((page) => (
        <section key={page.id} className="runtime-page">
          <h2>{page.title}</h2>
          {page.sections.map((section) => (
            <div key={section.id} className="runtime-section">
              <h3>{section.title}</h3>
              {section.rows.map((row) => (
                <div key={row.id} className="runtime-row">
                  {row.columns.map((column) => (
                    <div key={column.id} className="runtime-column" style={widthStyle(column)}>
                      {column.components.map((component) => (
                        <RuntimeField key={component.id} component={component} values={values} onChange={onValueChange} />
                      ))}
                    </div>
                  ))}
                </div>
              ))}
            </div>
          ))}
        </section>
      ))}
    </main>
  );
}
