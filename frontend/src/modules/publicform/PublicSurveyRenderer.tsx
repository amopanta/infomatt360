import { useMemo, useState } from 'react';
import { RuntimeField } from '../runtime/RuntimeField';
import { parseFieldConfig } from '../runtime/fieldConfig';
import { isFieldVisible, validateFormValues } from '../runtime/formLogic';
import { themeStyle } from '../runtime/RuntimeRenderer';
import type { RuntimeComponent, RuntimeFormValue, RuntimeFormValues, RuntimeSection, RuntimeTemplate } from '../runtime/types';

type Step = { pageTitle: string; section: RuntimeSection };

function components(section: RuntimeSection): RuntimeComponent[] {
  return section.rows.flatMap((row) => row.columns.flatMap((column) => column.components));
}

function missingRequired(step: Step, values: RuntimeFormValues): string | null {
  for (const component of components(step.section)) {
    const config = parseFieldConfig(component.config_json);
    if (!config.required || !isFieldVisible(component, values)) continue;
    const value = values[component.name];
    if (value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0)) return config.required_message || `Completa «${component.label}».`;
  }
  return null;
}

export function PublicSurveyRenderer({ template, values, onValueChange, onSubmit, submitting, serverMessage }: {
  template: RuntimeTemplate;
  values: RuntimeFormValues;
  onValueChange: (fieldName: string, value: RuntimeFormValue) => void;
  onSubmit: () => void;
  submitting: boolean;
  serverMessage: string;
}) {
  const steps = useMemo<Step[]>(() => template.pages.flatMap((page) => page.sections.map((section) => ({ pageTitle: page.title, section }))), [template]);
  const [stepIndex, setStepIndex] = useState(0);
  const [menuOpen, setMenuOpen] = useState(false);
  const [validationMessage, setValidationMessage] = useState('');
  const current = stepIndex > 0 ? steps[stepIndex - 1] : null;
  const total = steps.length;

  function navigate(next: number) {
    if (next > stepIndex && current) {
      const missing = missingRequired(current, values);
      if (missing) { setValidationMessage(missing); return; }
    }
    setValidationMessage('');
    setMenuOpen(false);
    setStepIndex(Math.max(0, Math.min(next, total)));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }

  function finish() {
    for (let index = 0; index < steps.length; index += 1) {
      const missing = missingRequired(steps[index], values);
      if (missing) { setStepIndex(index + 1); setValidationMessage(missing); return; }
    }
    const invalid = validateFormValues(template, values);
    if (invalid) { setValidationMessage(invalid); return; }
    setValidationMessage('');
    onSubmit();
  }

  return <div className="public-survey" style={themeStyle(template.theme_json)}>
    <header className="public-survey-topbar"><span>InfoMatt360</span><div><button type="button" aria-label="Imprimir formulario" title="Imprimir" onClick={() => window.print()}>▣</button><button type="button" aria-label="Abrir navegación" title="Navegación" onClick={() => setMenuOpen((open) => !open)}>☰</button></div></header>
    {menuOpen && <nav className="public-survey-menu" aria-label="Navegación del formulario"><button type="button" onClick={() => navigate(0)}>Inicio</button>{steps.map((step, index) => <button type="button" key={step.section.id} onClick={() => navigate(index + 1)}>{index + 1}. {step.section.title}</button>)}</nav>}
    <main className="public-survey-card">
      {stepIndex === 0 ? <div className="public-survey-intro"><h1>{template.name}</h1>{template.description && <p>{template.description}</p>}{!total && <p>Este formulario aún no tiene preguntas.</p>}<button type="button" className="public-survey-primary" disabled={!total} onClick={() => navigate(1)}>➜ Siguiente</button></div> : current && <div className="public-survey-step"><div className="public-survey-step-meta">Sección {stepIndex} de {total}{current.pageTitle !== current.section.title ? ` · ${current.pageTitle}` : ''}</div><h2>{current.section.title}</h2>{current.section.description && <p>{current.section.description}</p>}{current.section.rows.map((row) => <div key={row.id} className="runtime-row">{row.columns.map((column) => <div key={column.id} className="runtime-column" style={{ '--desktop-span': String(column.desktop_width || 12), '--tablet-span': String(column.tablet_width || 12), '--mobile-span': String(column.mobile_width || 12) } as React.CSSProperties}>{column.components.map((component) => <RuntimeField key={component.id} component={component} projectId="" values={values} onChange={onValueChange} uploadsDisabled />)}</div>)}</div>)}<div className="public-survey-main-actions">{stepIndex < total ? <button type="button" className="public-survey-primary" onClick={() => navigate(stepIndex + 1)}>➜ Siguiente</button> : <button type="button" className="public-survey-primary" disabled={submitting} onClick={finish}>{submitting ? 'Enviando…' : 'Enviar respuesta'}</button>}</div></div>}
      {(validationMessage || serverMessage) && <p className="public-survey-error" role="alert">{validationMessage || serverMessage}</p>}
      <footer className="public-survey-footer"><button type="button" aria-label="Paso anterior" disabled={stepIndex === 0} onClick={() => navigate(stepIndex - 1)}>↶</button><button type="button" onClick={() => navigate(0)}>Volver al principio</button><button type="button" onClick={() => navigate(total)}>Ir al final</button><button type="button" aria-label="Ir al final" onClick={() => navigate(total)}>➜</button></footer>
    </main>
  </div>;
}
