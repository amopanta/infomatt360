/**
 * Entrada sin conexión en la app de escritorio.
 *
 * Tras un inicio de sesión en línea se guarda una copia de la sesión
 * (usuario, proyectos y permisos, sin tokens). Si después el equipo arranca
 * sin red, el gestor entra con un PIN local y trabaja con los datos
 * descargados; al volver la conexión, la sesión real se renueva con la
 * cookie de refresco y se envía lo pendiente.
 *
 * El PIN nunca se guarda en claro: se deriva con PBKDF2-SHA256 y sal
 * aleatoria. Cinco intentos fallidos bloquean cinco minutos. La copia vence
 * a los OFFLINE_MAX_DAYS días sin conectarse, y cerrar sesión la borra.
 */

import { isDesktopApp } from '../desktop/desktopBridge';
import type { AuthSession } from './types';

export const OFFLINE_SESSION_KEY = 'infomatt360_offline_session';
const PIN_KEY_PREFIX = 'infomatt360_offline_pin:';
export const OFFLINE_MAX_DAYS = 7;
const MAX_ATTEMPTS = 5;
const LOCK_MS = 5 * 60 * 1000;
const ITERATIONS = 210_000;

export type OfflineSnapshot = { session: AuthSession; savedAt: string };
type StoredPin = { salt: string; hash: string; iterations: number; failures: number; lockedUntil: number };

export function saveOfflineSnapshot(session: AuthSession): void {
  if (!isDesktopApp()) return;
  const snapshot: OfflineSnapshot = { session, savedAt: new Date().toISOString() };
  localStorage.setItem(OFFLINE_SESSION_KEY, JSON.stringify(snapshot));
}

/** Copia vigente, o null si no hay, está dañada o venció. */
export function readOfflineSnapshot(): OfflineSnapshot | null {
  try {
    const parsed = JSON.parse(localStorage.getItem(OFFLINE_SESSION_KEY) ?? 'null') as OfflineSnapshot | null;
    if (!parsed?.session?.user_id || !Array.isArray(parsed.session.projects)) return null;
    return parsed;
  } catch {
    return null;
  }
}

export function offlineSnapshotExpired(snapshot: OfflineSnapshot, now = Date.now()): boolean {
  const savedAt = Date.parse(snapshot.savedAt);
  return !Number.isFinite(savedAt) || now - savedAt > OFFLINE_MAX_DAYS * 24 * 60 * 60 * 1000;
}

export function clearOfflineSnapshot(): void {
  localStorage.removeItem(OFFLINE_SESSION_KEY);
}

function readPin(userId: string): StoredPin | null {
  try {
    return JSON.parse(localStorage.getItem(PIN_KEY_PREFIX + userId) ?? 'null') as StoredPin | null;
  } catch {
    return null;
  }
}

function writePin(userId: string, pin: StoredPin): void {
  localStorage.setItem(PIN_KEY_PREFIX + userId, JSON.stringify(pin));
}

export function hasOfflinePin(userId: string): boolean {
  return Boolean(readPin(userId)?.hash);
}

export function isValidPin(pin: string): boolean {
  return /^\d{4,8}$/.test(pin);
}

function toHex(bytes: Uint8Array): string {
  return Array.from(bytes).map((byte) => byte.toString(16).padStart(2, '0')).join('');
}

function fromHex(hex: string): Uint8Array<ArrayBuffer> {
  return new Uint8Array((hex.match(/.{2}/g) ?? []).map((pair) => parseInt(pair, 16)));
}

async function derive(pin: string, salt: Uint8Array<ArrayBuffer>, iterations: number): Promise<string> {
  const key = await crypto.subtle.importKey('raw', new TextEncoder().encode(pin), 'PBKDF2', false, ['deriveBits']);
  const bits = await crypto.subtle.deriveBits({ name: 'PBKDF2', hash: 'SHA-256', salt, iterations }, key, 256);
  return toHex(new Uint8Array(bits));
}

export async function setOfflinePin(userId: string, pin: string, iterations = ITERATIONS): Promise<void> {
  if (!isValidPin(pin)) throw new Error('PIN inválido');
  const salt = crypto.getRandomValues(new Uint8Array(16));
  writePin(userId, { salt: toHex(salt), hash: await derive(pin, salt, iterations), iterations, failures: 0, lockedUntil: 0 });
}

export type PinCheck = { ok: true } | { ok: false; reason: 'missing' | 'locked' | 'wrong'; attemptsLeft: number };

export async function verifyOfflinePin(userId: string, pin: string, now = Date.now()): Promise<PinCheck> {
  const stored = readPin(userId);
  if (!stored?.hash) return { ok: false, reason: 'missing', attemptsLeft: 0 };
  if (stored.lockedUntil > now) return { ok: false, reason: 'locked', attemptsLeft: 0 };
  const hash = await derive(pin, fromHex(stored.salt), stored.iterations);
  if (hash === stored.hash) {
    writePin(userId, { ...stored, failures: 0, lockedUntil: 0 });
    return { ok: true };
  }
  const failures = stored.failures + 1;
  const locked = failures >= MAX_ATTEMPTS;
  writePin(userId, { ...stored, failures: locked ? 0 : failures, lockedUntil: locked ? now + LOCK_MS : 0 });
  return { ok: false, reason: locked ? 'locked' : 'wrong', attemptsLeft: locked ? 0 : MAX_ATTEMPTS - failures };
}
