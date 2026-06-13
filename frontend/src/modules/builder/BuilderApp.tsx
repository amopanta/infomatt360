import { useState } from 'react';
import { AppShell } from '../../components/AppShell';
import { BuilderCanvas } from './BuilderCanvas';
import { BuilderPalette } from './BuilderPalette';
import { createDefaultCharacterizationTemplate } from './createDefaultTemplate';

export function BuilderApp() {
  const [message, setMessage] = useState('');
  const [runtimeUrl, setRuntimeUrl] = useState('');
  const projectId = localStorage.getItem('infomatt360_project_id') ?? '';

  async function createMvpTemplate() {
    if (!projectId) {
      setMessage('Falta infomatt360_project_id en localStorage.');
      return;
    }
    const template = await createDefaultCharacterizationTemplate(projectId);
    const url = `/runtime/${template.id}`;
    setRuntimeUrl(url);
    setMessage(`Plantilla creada: ${template.id}`);
  }

  return (
    <AppShell title="Constructor de Formularios">
      <div className="builder-layout">
        <BuilderPalette />
        <div>
          <div className="builder-connect-panel">
            <strong>Plantilla MVP</strong>
            <p>Crea una caracterizacion base conectada al backend Builder.</p>
            <button onClick={createMvpTemplate}>Crear plantilla de caracterizacion</button>
            {message ? <span>{message}</span> : null}
            {runtimeUrl ? <a href={runtimeUrl}>Abrir Runtime</a> : null}
          </div>
          <BuilderCanvas />
        </div>
      </div>
    </AppShell>
  );
}
