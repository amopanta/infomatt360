import type { BuilderPreviewSection } from './types';

const sections: BuilderPreviewSection[] = [
  {
    id: 'general',
    title: 'Informacion General',
    fields: [
      { id: 'name', type: 'TEXT', label: 'Nombre completo', placeholder: 'Escribe el nombre completo' },
      { id: 'document', type: 'TEXT', label: 'Numero de documento', placeholder: 'Ingresa el documento' },
      { id: 'municipality', type: 'TEXT', label: 'Municipio', placeholder: 'Municipio' },
      { id: 'observations', type: 'TEXTAREA', label: 'Observaciones', placeholder: 'Observaciones adicionales' },
    ],
  },
];

export function BuilderCanvas() {
  return (
    <section className="builder-canvas">
      <div className="builder-toolbar">
        <div>
          <h2>Constructor de Formularios</h2>
          <p>Diseno visual alineado a INFOMATT.</p>
        </div>
        <div className="builder-actions">
          <button>Vista previa</button>
          <button className="primary">Publicar</button>
        </div>
      </div>
      {sections.map((section) => (
        <article key={section.id} className="builder-section-card">
          <header>{section.title}</header>
          <div className="builder-grid">
            {section.fields.map((field) => (
              <label key={field.id} className="builder-field-card">
                <span>{field.label}</span>
                {field.type === 'TEXTAREA' ? <textarea placeholder={field.placeholder} /> : <input placeholder={field.placeholder} />}
              </label>
            ))}
          </div>
        </article>
      ))}
    </section>
  );
}
