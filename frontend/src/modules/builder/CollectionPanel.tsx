import { useState } from 'react';
import { createPublicLink } from '../admin/publicLinksApi';
import type { TemplateSummary } from '../records/api';

type CollectionMode = 'offline' | 'onlineMultiple' | 'onlineSingle' | 'perRespondent' | 'embed' | 'readOnly' | 'android';

const descriptions: Record<CollectionMode, string> = {
  offline: 'Captura con cuenta en la aplicación web. Abre el formulario mientras tienes conexión; si se corta, las respuestas quedan pendientes y se sincronizan al volver.',
  onlineMultiple: 'Crea un enlace público que admite varios envíos mientras el formulario esté activo.',
  onlineSingle: 'Crea un enlace público que se cierra tras recibir una respuesta.',
  perRespondent: 'Crea un enlace individual de un envío para cada código de encuestado. El enlace limita envíos; no verifica la identidad de quien lo abre.',
  embed: 'Crea un enlace público y un código iframe para insertar el formulario en otra página web.',
  readOnly: 'Abre una vista previa para el equipo con acceso a InfoMatt360. No guarda respuestas.',
  android: 'Abre el formulario de campo en Android. Puedes instalar InfoMatt360 desde el menú de Chrome como aplicación web.',
};

export function CollectionPanel({ template, onIssued }: { template: TemplateSummary; onIssued: () => void }) {
  const [mode, setMode] = useState<CollectionMode>('onlineMultiple');
  const [respondentCode, setRespondentCode] = useState('');
  const [issuedUrl, setIssuedUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const isLinkMode = ['onlineMultiple', 'onlineSingle', 'perRespondent', 'embed'].includes(mode);
  const runtimeUrl = `${window.location.origin}/runtime/${template.id}`;
  const previewUrl = `${runtimeUrl}?preview=1`;
  const embedCode = issuedUrl ? `<iframe src="${issuedUrl}" title="${template.name.replace(/"/g, '&quot;')}" width="100%" height="760" style="border:0" loading="lazy"></iframe>` : '';

  async function copy(value: string) {
    try { await navigator.clipboard.writeText(value); setMessage('Copiado al portapapeles.'); }
    catch { setMessage('Selecciona el texto y cópialo manualmente.'); }
  }

  async function generate() {
    const code = respondentCode.trim().toLowerCase();
    if (mode === 'perRespondent' && !code) { setMessage('Escribe un código para el encuestado.'); return; }
    setBusy(true);
    setMessage('');
    try {
      const issued = await createPublicLink({
        templateId: template.id,
        label: mode === 'perRespondent' ? `encuestado:${code}` : undefined,
        maxSubmissions: mode === 'onlineSingle' || mode === 'perRespondent' ? 1 : undefined,
      });
      setIssuedUrl(`${window.location.origin}/public-form/${issued.token}`);
      setMessage('Enlace creado. Cópialo ahora: el código completo se muestra una sola vez.');
      onIssued();
    } catch (error) { setMessage(error instanceof Error ? error.message : 'No fue posible generar el enlace.'); }
    finally { setBusy(false); }
  }

  return <div className="forms-collect">
    <h3>Recolectar datos</h3>
    <label>Modo de captura
      <select value={mode} onChange={(event) => { setMode(event.target.value as CollectionMode); setIssuedUrl(''); setMessage(''); }}>
        <option value="offline">En línea y sin conexión (varios envíos)</option>
        <option value="onlineMultiple">Solo en línea (múltiples envíos)</option>
        <option value="onlineSingle">Solo en línea (único envío)</option>
        <option value="perRespondent">Solo en línea (uno por encuestado/a)</option>
        <option value="embed">Código de formulario web insertable</option>
        <option value="readOnly">Solo lectura</option>
        <option value="android">Aplicación Android</option>
      </select>
    </label>
    <p>{descriptions[mode]}</p>
    {mode === 'perRespondent' && <label>Código del encuestado<input value={respondentCode} maxLength={100} placeholder="Ejemplo: hogar-001" onChange={(event) => setRespondentCode(event.target.value)} /></label>}
    {isLinkMode && <button type="button" disabled={busy || template.status !== 'published' || template.availability === 'closed'} onClick={() => void generate()}>{busy ? 'Generando…' : 'Generar enlace'}</button>}
    {mode === 'offline' && <div className="forms-collect-guide"><a href={runtimeUrl} target="_blank" rel="noreferrer">Abrir formulario de campo</a><small>Requiere iniciar sesión y abrir el formulario una vez con conexión. Mantén la sesión abierta durante la captura sin red.</small></div>}
    {mode === 'readOnly' && <div className="forms-collect-guide"><a href={previewUrl} target="_blank" rel="noreferrer">Abrir vista de solo lectura</a><small>El acceso requiere una cuenta de InfoMatt360.</small></div>}
    {mode === 'android' && <div className="forms-collect-guide"><a href={runtimeUrl} target="_blank" rel="noreferrer">Abrir en Android</a><small>En Chrome para Android, abre el menú ⋮ y elige «Instalar aplicación» o «Agregar a pantalla principal». Es una aplicación web instalable.</small></div>}
    {issuedUrl && <div className="forms-collect-link"><input readOnly aria-label="Enlace público recién creado" value={issuedUrl} onFocus={(event) => event.target.select()} /><button type="button" onClick={() => void copy(issuedUrl)}>Copiar</button><a href={issuedUrl} target="_blank" rel="noreferrer">Abrir</a></div>}
    {mode === 'embed' && embedCode && <label className="forms-embed-code">Código para insertar<textarea readOnly rows={3} value={embedCode} onFocus={(event) => event.target.select()} /><button type="button" onClick={() => void copy(embedCode)}>Copiar código</button></label>}
    {message && <p role="status">{message}</p>}
  </div>;
}
