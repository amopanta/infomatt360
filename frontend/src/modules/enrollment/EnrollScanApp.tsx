import jsQR from 'jsqr';
import { useEffect, useRef, useState } from 'react';
import { BrandLogo } from '../../components/BrandLogo';
import { extractTokenFromScannedUrl, validateEnrollmentQr } from './api';
import type { EnrollmentValidation } from './api';

type ScanStatus = 'checking-url' | 'starting-camera' | 'scanning' | 'validating' | 'success' | 'error';

function deviceFingerprint(): string {
  const key = 'infomatt360_device_fingerprint';
  let value = localStorage.getItem(key);
  if (!value) {
    value = crypto.randomUUID();
    localStorage.setItem(key, value);
  }
  return value;
}

export function EnrollScanApp() {
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const rafRef = useRef<number>(0);
  const [status, setStatus] = useState<ScanStatus>('checking-url');
  const [message, setMessage] = useState('');
  const [result, setResult] = useState<EnrollmentValidation | null>(null);

  useEffect(() => {
    const tokenFromUrl = new URLSearchParams(window.location.search).get('token');
    if (tokenFromUrl) {
      void validate(tokenFromUrl);
      return;
    }
    void startCamera();
    return () => stopCamera();
  }, []);

  async function validate(token: string) {
    setStatus('validating');
    try {
      const validation = await validateEnrollmentQr(token, deviceFingerprint());
      setResult(validation);
      setStatus('success');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible validar el codigo.');
      setStatus('error');
    } finally {
      stopCamera();
    }
  }

  async function startCamera() {
    setStatus('starting-camera');
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setStatus('scanning');
      scanFrame();
    } catch {
      setMessage('No fue posible acceder a la camara. Revisa los permisos del navegador.');
      setStatus('error');
    }
  }

  function stopCamera() {
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (rafRef.current) cancelAnimationFrame(rafRef.current);
  }

  function scanFrame() {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas || video.readyState !== video.HAVE_ENOUGH_DATA) {
      rafRef.current = requestAnimationFrame(scanFrame);
      return;
    }
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const context = canvas.getContext('2d');
    if (!context) return;
    context.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, imageData.width, imageData.height);
    if (code) {
      const token = extractTokenFromScannedUrl(code.data);
      if (token) {
        void validate(token);
        return;
      }
    }
    rafRef.current = requestAnimationFrame(scanFrame);
  }

  function retry() {
    setResult(null);
    setMessage('');
    void startCamera();
  }

  return (
    <div className="auth-page">
      <div className="auth-card enroll-scan-card">
        <BrandLogo />
        <h1>Enrolamiento por QR</h1>
        {status === 'scanning' || status === 'starting-camera' ? (
          <>
            <p>Apunta la camara al codigo QR generado por tu administrador.</p>
            <video ref={videoRef} className="enroll-scan-video" muted playsInline />
            <canvas ref={canvasRef} style={{ display: 'none' }} />
          </>
        ) : null}
        {status === 'validating' ? <p>Validando codigo...</p> : null}
        {status === 'success' && result ? (
          <div>
            <p role="status">Dispositivo enrolado correctamente.</p>
            <small>Proyecto: {result.project_id}</small>
          </div>
        ) : null}
        {status === 'error' ? (
          <div>
            <p role="alert">{message}</p>
            <button onClick={retry}>Intentar de nuevo</button>
          </div>
        ) : null}
        <a href="/">Volver al ingreso</a>
      </div>
    </div>
  );
}
