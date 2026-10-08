import { afterEach, expect, it, vi } from 'vitest';
import { refreshAccessToken } from './api';

vi.mock('./session', () => ({ currentAccessToken: () => '', setAccessToken: vi.fn() }));
afterEach(() => vi.unstubAllGlobals());

it('shares concurrent refresh calls instead of reusing a rotating cookie', async () => {
  let resolve!: (value: unknown) => void;
  const fetchMock = vi.fn(() => new Promise((done) => { resolve = done; }));
  vi.stubGlobal('fetch', fetchMock);
  const first = refreshAccessToken();
  const second = refreshAccessToken();
  expect(fetchMock).toHaveBeenCalledTimes(1);
  resolve({ ok: true, json: async () => ({ access_token: 'renewed' }) });
  expect(await Promise.all([first, second])).toEqual(['renewed', 'renewed']);
  fetchMock.mockImplementation(async () => ({ ok: true, json: async () => ({ access_token: 'next' }) }) as never);
  expect(await refreshAccessToken()).toBe('next');
  expect(fetchMock).toHaveBeenCalledTimes(2);
});

it('releases the refresh lock after a failure so a later attempt can run', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce({ ok: false }).mockResolvedValueOnce({ ok: true, json: async () => ({ access_token: 'retry' }) });
  vi.stubGlobal('fetch', fetchMock);
  await expect(refreshAccessToken()).rejects.toThrow('La sesión expiró');
  expect(await refreshAccessToken()).toBe('retry');
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
