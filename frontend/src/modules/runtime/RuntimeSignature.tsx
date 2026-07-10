import { useEffect, useRef, useState } from 'react';

import { uploadRuntimeFile } from './api';
import { pointerToCanvasPoint } from './signatureEngine';
import type { RuntimeFileValue } from './types';

type Props = {
  id: string;
  name: string;
  label: string;
  projectId: string;
  required: boolean;
  value?: RuntimeFileValue | null;
  onChange: (value: RuntimeFileValue) => void;
};

function canvasBlob(canvas: HTMLCanvasElement): Promise<Blob> {
  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => blob ? resolve(blob) : reject(new Error('No fue posible generar la firma.')), 'image/png');
  });
}

export function RuntimeSignature({ id, name, label, projectId, required, value, onChange }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const drawingRef = useRef(false);
  const [hasInk, setHasInk] = useState(false);
  const [status, setStatus] = useState(value ? 'Firma cargada.' : '');

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const bounds = canvas.getBoundingClientRect();
    const ratio = Math.max(1, window.devicePixelRatio || 1);
    canvas.width = Math.max(1, Math.round(bounds.width * ratio));
    canvas.height = Math.max(1, Math.round(bounds.height * ratio));
    const context = canvas.getContext('2d');
    if (context) {
      context.strokeStyle = '#0a2540';
      context.lineWidth = 2.5 * ratio;
      context.lineCap = 'round';
      context.lineJoin = 'round';
    }
  }, []);

  function point(event: React.PointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return pointerToCanvasPoint(event.clientX, event.clientY, bounds, canvas.width, canvas.height);
  }

  function startDrawing(event: React.PointerEvent<HTMLCanvasElement>) {
    const context = event.currentTarget.getContext('2d');
    if (!context) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    const next = point(event);
    context.beginPath();
    context.moveTo(next.x, next.y);
    drawingRef.current = true;
  }

  function draw(event: React.PointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current) return;
    const context = event.currentTarget.getContext('2d');
    if (!context) return;
    const next = point(event);
    context.lineTo(next.x, next.y);
    context.stroke();
    setHasInk(true);
  }

  function stopDrawing(event: React.PointerEvent<HTMLCanvasElement>) {
    drawingRef.current = false;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  }

  function clear() {
    const canvas = canvasRef.current;
    canvas?.getContext('2d')?.clearRect(0, 0, canvas.width, canvas.height);
    setHasInk(false);
    setStatus('Lienzo limpio.');
  }

  async function confirm() {
    const canvas = canvasRef.current;
    if (!canvas || !hasInk || !projectId) return;
    setStatus('Guardando firma...');
    try {
      const blob = await canvasBlob(canvas);
      const file = new File([blob], `firma-${name}.png`, { type: 'image/png' });
      const uploaded = await uploadRuntimeFile(projectId, 'SIGNATURE', file);
      onChange(uploaded);
      setStatus('Firma cargada correctamente.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'No fue posible cargar la firma.');
    }
  }

  return (
    <fieldset className="runtime-signature">
      <legend>{label}{required ? ' *' : ''}</legend>
      <canvas
        ref={canvasRef}
        id={id}
        aria-label={label}
        onPointerDown={startDrawing}
        onPointerMove={draw}
        onPointerUp={stopDrawing}
        onPointerCancel={stopDrawing}
      />
      <div className="runtime-signature-actions">
        <button type="button" onClick={clear}>Limpiar</button>
        <button type="button" disabled={!hasInk} onClick={() => void confirm()}>Confirmar firma</button>
      </div>
      {value ? <small>{value.name} ({value.size_bytes} bytes)</small> : null}
      {status ? <small role="status">{status}</small> : null}
    </fieldset>
  );
}

