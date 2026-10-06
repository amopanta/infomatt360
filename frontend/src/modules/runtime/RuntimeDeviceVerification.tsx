import { useState } from 'react';

import { beginDeviceVerification, finishDeviceVerification } from './api';
import type { RuntimeDeviceVerificationValue } from './types';

type Props = {
  id: string;
  componentId: string;
  templateId: string;
  label: string;
  required: boolean;
  value: RuntimeDeviceVerificationValue | null;
  onChange: (value: RuntimeDeviceVerificationValue) => void;
};

function decodeBase64Url(value: string): ArrayBuffer {
  const encoded = value.replace(/-/g, '+').replace(/_/g, '/');
  const binary = atob(encoded.padEnd(Math.ceil(encoded.length / 4) * 4, '='));
  const bytes = Uint8Array.from(binary, (character) => character.charCodeAt(0));
  return bytes.buffer;
}

function encodeBase64Url(value: ArrayBuffer): string {
  const bytes = new Uint8Array(value);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

function serializeCredential(credential: PublicKeyCredential): Record<string, unknown> {
  const response = credential.response;
  const common = {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
  };
  if (response instanceof AuthenticatorAttestationResponse) {
    return { ...common, response: {
      clientDataJSON: encodeBase64Url(response.clientDataJSON),
      attestationObject: encodeBase64Url(response.attestationObject),
      transports: response.getTransports(),
    } };
  }
  if (response instanceof AuthenticatorAssertionResponse) {
    return { ...common, response: {
      clientDataJSON: encodeBase64Url(response.clientDataJSON),
      authenticatorData: encodeBase64Url(response.authenticatorData),
      signature: encodeBase64Url(response.signature),
      userHandle: response.userHandle ? encodeBase64Url(response.userHandle) : null,
    } };
  }
  throw new Error('El dispositivo devolvió una respuesta no reconocida.');
}

export function RuntimeDeviceVerification({ id, componentId, templateId, label, required, value, onChange }: Props) {
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');

  async function verify(registerThisDevice = false) {
    if (!window.isSecureContext || !window.PublicKeyCredential || !navigator.credentials) {
      setStatus('La verificación del dispositivo requiere un móvil compatible y una conexión HTTPS.');
      return;
    }
    if (!navigator.onLine) {
      setStatus('Conéctate a internet para verificar el dispositivo antes de enviar el formulario.');
      return;
    }
    setBusy(true);
    setStatus('Esperando confirmación del dispositivo...');
    try {
      const options = await beginDeviceVerification(templateId, componentId, registerThisDevice);
      const raw = options.public_key as Record<string, any>;
      let credential: Credential | null;
      if (options.operation === 'register') {
        credential = await navigator.credentials.create({ publicKey: {
          ...raw,
          challenge: decodeBase64Url(raw.challenge),
          user: { ...raw.user, id: decodeBase64Url(raw.user.id) },
          excludeCredentials: (raw.excludeCredentials ?? []).map((item: Record<string, string>) => ({ ...item, id: decodeBase64Url(item.id) })),
        } as PublicKeyCredentialCreationOptions });
      } else {
        credential = await navigator.credentials.get({ publicKey: {
          ...raw,
          challenge: decodeBase64Url(raw.challenge),
          allowCredentials: (raw.allowCredentials ?? []).map((item: Record<string, string>) => ({ ...item, id: decodeBase64Url(item.id) })),
        } as PublicKeyCredentialRequestOptions });
      }
      if (!(credential instanceof PublicKeyCredential)) throw new Error('El dispositivo canceló la verificación.');
      const proof = await finishDeviceVerification(options.verification_id, serializeCredential(credential));
      onChange(proof);
      setStatus('Identidad del usuario confirmada en este dispositivo. Guarda el formulario ahora.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'No fue posible verificar el dispositivo.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <fieldset className="runtime-field-group" id={id}>
      <legend>{label}{required ? ' *' : ''}</legend>
      <p>Confirma tu identidad con la seguridad del móvil. Según el equipo, puede usar huella, rostro o PIN. No se guarda la imagen de tu huella ni se verifica la identidad del participante.</p>
      <button type="button" disabled={busy} onClick={() => void verify()}>{busy ? 'Verificando...' : value ? 'Verificar de nuevo' : 'Verificar en este móvil'}</button>
      <button type="button" disabled={busy} onClick={() => void verify(true)}>Registrar este móvil</button>
      {value ? <small>Verificación confirmada. Vuelve a verificar si vence antes de enviar.</small> : null}
      {status ? <small role="status">{status}</small> : null}
    </fieldset>
  );
}
