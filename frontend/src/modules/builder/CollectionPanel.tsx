import { useState } from 'react';
import { createPublicLink } from '../admin/publicLinksApi';
import type { TemplateSummary } from '../records/api';
import { useI18n } from '../../i18n';

type CollectionMode = 'offline' | 'onlineMultiple' | 'onlineSingle' | 'perRespondent' | 'embed' | 'readOnly' | 'android';

export function CollectionPanel({ template, onIssued }: { template: TemplateSummary; onIssued: () => void }) {
  const { t } = useI18n();
  const descriptions: Record<CollectionMode, string> = {
    offline: t('builder.collection.offlineDesc'),
    onlineMultiple: t('builder.collection.onlineMultipleDesc'),
    onlineSingle: t('builder.collection.onlineSingleDesc'),
    perRespondent: t('builder.collection.perRespondentDesc'),
    embed: t('builder.collection.embedDesc'),
    readOnly: t('builder.collection.readOnlyDesc'),
    android: t('builder.collection.androidDesc'),
  };

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
    try { await navigator.clipboard.writeText(value); setMessage(t('builder.collection.copiedToClipboard')); }
    catch { setMessage(t('builder.collection.copyManually')); }
  }

  async function generate() {
    const code = respondentCode.trim().toLowerCase();
    if (mode === 'perRespondent' && !code) { setMessage(t('builder.collection.respondentCodeRequired')); return; }
    setBusy(true);
    setMessage('');
    try {
      const issued = await createPublicLink({
        templateId: template.id,
        label: mode === 'perRespondent' ? `encuestado:${code}` : undefined,
        maxSubmissions: mode === 'onlineSingle' || mode === 'perRespondent' ? 1 : undefined,
      });
      setIssuedUrl(`${window.location.origin}/public-form/${issued.token}`);
      setMessage(t('builder.collection.linkCreated'));
      onIssued();
    } catch (error) { setMessage(error instanceof Error ? error.message : t('builder.collection.linkFailed')); }
    finally { setBusy(false); }
  }

  return <div className="forms-collect">
    <h3>{t('builder.collection.title')}</h3>
    <label>{t('builder.collection.captureMode')}
      <select value={mode} onChange={(event) => { setMode(event.target.value as CollectionMode); setIssuedUrl(''); setMessage(''); }}>
        <option value="offline">{t('builder.collection.offlineOption')}</option>
        <option value="onlineMultiple">{t('builder.collection.onlineMultipleOption')}</option>
        <option value="onlineSingle">{t('builder.collection.onlineSingleOption')}</option>
        <option value="perRespondent">{t('builder.collection.perRespondentOption')}</option>
        <option value="embed">{t('builder.collection.embedOption')}</option>
        <option value="readOnly">{t('builder.collection.readOnlyOption')}</option>
        <option value="android">{t('builder.collection.androidOption')}</option>
      </select>
    </label>
    <p>{descriptions[mode]}</p>
    {mode === 'perRespondent' && <label>{t('builder.collection.respondentCode')}<input value={respondentCode} maxLength={100} placeholder={t('builder.collection.respondentPlaceholder')} onChange={(event) => setRespondentCode(event.target.value)} /></label>}
    {isLinkMode && <button type="button" disabled={busy || template.status !== 'published' || template.availability === 'closed'} onClick={() => void generate()}>{busy ? t('builder.collection.generating') : t('builder.collection.generateLink')}</button>}
    {mode === 'offline' && <div className="forms-collect-guide"><a href={runtimeUrl} target="_blank" rel="noreferrer">{t('builder.collection.openFieldForm')}</a><small>{t('builder.collection.offlineGuide')}</small></div>}
    {mode === 'readOnly' && <div className="forms-collect-guide"><a href={previewUrl} target="_blank" rel="noreferrer">{t('builder.collection.openReadOnly')}</a><small>{t('builder.collection.readOnlyGuide')}</small></div>}
    {mode === 'android' && <div className="forms-collect-guide"><a href={runtimeUrl} target="_blank" rel="noreferrer">{t('builder.collection.openAndroid')}</a><small>{t('builder.collection.androidGuide')}</small></div>}
    {issuedUrl && <div className="forms-collect-link"><input readOnly aria-label={t('builder.collection.publicLinkAria')} value={issuedUrl} onFocus={(event) => event.target.select()} /><button type="button" onClick={() => void copy(issuedUrl)}>{t('builder.collection.copy')}</button><a href={issuedUrl} target="_blank" rel="noreferrer">{t('builder.collection.open')}</a></div>}
    {mode === 'embed' && embedCode && <label className="forms-embed-code">{t('builder.collection.embedCodeLabel')}<textarea readOnly rows={3} value={embedCode} onFocus={(event) => event.target.select()} /><button type="button" onClick={() => void copy(embedCode)}>{t('builder.collection.copyCode')}</button></label>}
    {message && <p role="status">{message}</p>}
  </div>;
}
