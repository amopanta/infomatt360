import { useState } from 'react';
import { RuntimeField } from './RuntimeField';
import { RuntimeStepper } from './RuntimeStepper';
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
  const [activePageIndex, setActivePageIndex] = useState(0);
  const activePage = template.pages[activePageIndex];

  if (!activePage) {
    return <main className="runtime-shell"><h1>{template.name}</h1><p>Sin paginas configuradas.</p></main>;
  }

  return (
    <main className="runtime-shell">
      <h1>{template.name}</h1>
      <RuntimeStepper pages={template.pages} activePageIndex={activePageIndex} onSelect={setActivePageIndex} />
      <section key={activePage.id} className="runtime-page">
        <h2>{activePage.title}</h2>
        {activePage.sections.map((section) => (
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
      <div className="runtime-page-actions">
        <button disabled={activePageIndex === 0} onClick={() => setActivePageIndex((current) => current - 1)}>Anterior</button>
        <button disabled={activePageIndex >= template.pages.length - 1} onClick={() => setActivePageIndex((current) => current + 1)}>Siguiente</button>
      </div>
    </main>
  );
}
