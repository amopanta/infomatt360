import { describe, expect, it } from 'vitest';
import { extractTokenFromScannedUrl } from './api';

describe('extractTokenFromScannedUrl', () => {
  it('extrae el token de una URL de enrolamiento valida', () => {
    expect(extractTokenFromScannedUrl('http://localhost:5173/enroll?token=abc123')).toBe('abc123');
  });

  it('retorna null si la URL no tiene parametro token', () => {
    expect(extractTokenFromScannedUrl('http://localhost:5173/enroll')).toBeNull();
  });

  it('retorna null si el texto escaneado no es una URL', () => {
    expect(extractTokenFromScannedUrl('no es una url')).toBeNull();
  });
});
