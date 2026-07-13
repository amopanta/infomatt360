import { useEffect, useState } from 'react';
import { RuntimeField } from './RuntimeField';
import { RuntimeSectionNavigator } from './RuntimeSectionNavigator';
import { RuntimeStepper } from './RuntimeStepper';
import type { RuntimeFormValue, RuntimeFormValues, RuntimeTemplate } from './types';

type Props = {
  template: RuntimeTemplate;
  projectId: string;
  values: RuntimeFormValues;
  onValueChange: (fieldName: string, value: RuntimeFormValue) => void;
  uploadsDisabled?: boolean;
};

function widthStyle(column: { desktop_width: number; tablet_width: number; mobile_width: number }) {
  return {
    '--desktop-span': String(column.desktop_width || 12),
    '--tablet-span': String(column.tablet_width || 12),
    '--mobile-span': String(column.mobile_width || 12),
  } as React.CSSProperties;
}

export function themeStyle(themeJson?: string | null) {
  try {
    const theme = JSON.parse(themeJson ?? '{}') as Record<string, unknown>;
    return {
      '--form-primary': typeof theme.primaryColor === 'string' ? theme.primaryColor : '#0066cc',
      '--form-accent': typeof theme.accentColor === 'string' ? theme.accentColor : '#00c2ff',
      '--form-background': typeof theme.backgroundColor === 'string' ? theme.backgroundColor : '#ffffff',
      '--form-radius': typeof theme.radius === 'string' ? theme.radius : '18px',
    } as React.CSSProperties;
  } catch {
    return {} as React.CSSProperties;
  }
}

export function RuntimeRenderer({ template, projectId, values, onValueChange, uploadsDisabled }: Props) {
  const [activePageIndex, setActivePageIndex] = useState(0);
  const [activeSectionIndex, setActiveSectionIndex] = useState(0);
  const activePage = template.pages[activePageIndex];
  const activeSection = activePage?.sections[activeSectionIndex];

  useEffect(() => {
    setActiveSectionIndex(0);
  }, [activePageIndex]);

  if (!activePage) {
    return <main className="runtime-shell" style={themeStyle(template.theme_json)}><h1>{template.name}</h1><p>Sin paginas configuradas.</p></main>;
  }

  return (
    <main className="runtime-shell" style={themeStyle(template.theme_json)}>
      <h1>{template.name}</h1>
      <RuntimeStepper pages={template.pages} activePageIndex={activePageIndex} onSelect={setActivePageIndex} />
      <section key={activePage.id} className="runtime-page">
        <h2>{activePage.title}</h2>
        <RuntimeSectionNavigator sections={activePage.sections} activeSectionIndex={activeSectionIndex} onSelect={setActiveSectionIndex} />
        {activeSection ? (
          <div key={activeSection.id} className="runtime-section">
            <h3>{activeSection.title}</h3>
            {activeSection.rows.map((row) => (
              <div key={row.id} className="runtime-row">
                {row.columns.map((column) => (
                  <div key={column.id} className="runtime-column" style={widthStyle(column)}>
                    {column.components.map((component) => (
                      <RuntimeField key={component.id} component={component} projectId={projectId} values={values} onChange={onValueChange} uploadsDisabled={uploadsDisabled} />
                    ))}
                  </div>
                ))}
              </div>
            ))}
          </div>
        ) : <p>Sin secciones configuradas.</p>}
      </section>
      <div className="runtime-page-actions">
        <button disabled={activePageIndex === 0} onClick={() => setActivePageIndex((current) => current - 1)}>Anterior</button>
        <button disabled={activePageIndex >= template.pages.length - 1} onClick={() => setActivePageIndex((current) => current + 1)}>Siguiente</button>
      </div>
    </main>
  );
}
