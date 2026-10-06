// Carga autenticada y acotada para un proyecto de pruebas de InfoMatt360.
// Ver loadtest/FUNCTIONAL_FLOWS.md antes de habilitar escrituras.
import http from 'k6/http';
import { check, sleep } from 'k6';
import exec from 'k6/execution';
import { SharedArray } from 'k6/data';
import { Counter, Rate } from 'k6/metrics';

const BASE = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const PROFILE = (__ENV.PROFILE || 'read').toLowerCase();
const PROJECT = __ENV.PROJECT_ID || '';
const TEMPLATE = __ENV.TEMPLATE_ID || '';
const RUN_ID = __ENV.RUN_ID || '';
const SHARD_OFFSET = Number(__ENV.SHARD_OFFSET || 0);
const BATCH_SIZE = Number(__ENV.SYNC_BATCH_SIZE || 5);
const READ_VUS = Number(__ENV.READ_VUS || 2);
const WRITE_VUS = Number(__ENV.WRITE_VUS || 2);
const EXPORT_VUS = Number(__ENV.EXPORT_VUS || 1);
function participantIds(fileVariable, listVariable) {
  const raw = __ENV[fileVariable] ? open(__ENV[fileVariable]) : (__ENV[listVariable] || '');
  return raw.split(/[\r\n,]+/).map((value) => value.trim()).filter(Boolean);
}
const CAPTURE_IDS = new SharedArray('capture participants', () => participantIds('CAPTURE_IDS_FILE', 'CAPTURE_PARTICIPANT_IDS'));
const SYNC_IDS = new SharedArray('sync participants', () => participantIds('SYNC_IDS_FILE', 'SYNC_PARTICIPANT_IDS'));
const WRITES = PROFILE === 'capture' || PROFILE === 'sync' || PROFILE === 'all';
const READS = PROFILE === 'read' || PROFILE === 'all';
const EXPORTS = PROFILE === 'export' || PROFILE === 'all';
const CAPTURES = PROFILE === 'capture' || PROFILE === 'all';
const SYNCS = PROFILE === 'sync' || PROFILE === 'all';
const flowFailures = new Rate('flow_failures');
const recordsCreated = new Counter('loadtest_records_created');
const recordsFailed = new Counter('loadtest_records_failed');

function required(condition, message) {
  if (!condition) throw new Error(message);
}

required(['read', 'capture', 'sync', 'export', 'all'].includes(PROFILE), 'PROFILE invalido');
required(PROJECT && TEMPLATE, 'Indica PROJECT_ID y TEMPLATE_ID de un proyecto de pruebas');
required(Number.isInteger(SHARD_OFFSET) && SHARD_OFFSET >= 0, 'SHARD_OFFSET debe ser entero no negativo');
required(Number.isInteger(BATCH_SIZE) && BATCH_SIZE >= 1 && BATCH_SIZE <= 20, 'SYNC_BATCH_SIZE debe estar entre 1 y 20');
required(Number.isInteger(READ_VUS) && READ_VUS >= 1, 'READ_VUS invalido');
required(Number.isInteger(WRITE_VUS) && WRITE_VUS >= 1, 'WRITE_VUS invalido');
required(Number.isInteger(EXPORT_VUS) && EXPORT_VUS >= 1 && EXPORT_VUS <= 5, 'EXPORT_VUS debe estar entre 1 y 5');

let values = null;
if (WRITES) {
  required(__ENV.ENABLE_WRITES === 'true' && __ENV.TEST_PROJECT_CONFIRMED === 'yes', 'La escritura requiere ENABLE_WRITES=true y TEST_PROJECT_CONFIRMED=yes');
  required(/^[A-Za-z0-9_-]{8,40}$/.test(RUN_ID), 'RUN_ID debe tener 8-40 caracteres alfanumericos, guion o guion bajo');
  try { values = JSON.parse(__ENV.VALUES_JSON || ''); } catch (_) { throw new Error('VALUES_JSON debe ser un objeto JSON valido con valores de campos reales'); }
  required(values && typeof values === 'object' && !Array.isArray(values) && Object.keys(values).length > 0, 'VALUES_JSON debe contener los campos validos de la plantilla de pruebas');
  required(!CAPTURES || CAPTURE_IDS.length > 0, 'Faltan CAPTURE_PARTICIPANT_IDS');
  required(!SYNCS || SYNC_IDS.length > 0, 'Faltan SYNC_PARTICIPANT_IDS');
  required(new Set([...CAPTURE_IDS, ...SYNC_IDS]).size === CAPTURE_IDS.length + SYNC_IDS.length, 'Los participantes de captura y sincronizacion deben ser distintos');
}

const scenarios = {};
if (READS) scenarios.read = { executor: 'ramping-vus', exec: 'readFlow', startVUs: 0,
  stages: [{ duration: '15s', target: READ_VUS }, { duration: __ENV.READ_DURATION || '30s', target: READ_VUS }, { duration: '15s', target: 0 }] };
if (CAPTURES) scenarios.capture = { executor: 'shared-iterations', exec: 'captureFlow',
  vus: Math.min(WRITE_VUS, CAPTURE_IDS.length), iterations: CAPTURE_IDS.length, maxDuration: '10m' };
if (SYNCS) scenarios.sync = { executor: 'shared-iterations', exec: 'syncFlow',
  vus: Math.min(WRITE_VUS, Math.ceil(SYNC_IDS.length / BATCH_SIZE)), iterations: Math.ceil(SYNC_IDS.length / BATCH_SIZE), maxDuration: '10m' };
if (EXPORTS) scenarios.export = { executor: 'constant-vus', exec: 'exportFlow', vus: EXPORT_VUS, duration: __ENV.EXPORT_DURATION || '30s' };

export const options = {
  scenarios,
  thresholds: {
    flow_failures: ['rate<0.01'],
    'http_req_duration{endpoint:search}': ['p(95)<500', 'p(99)<1500'],
    'http_req_duration{endpoint:capture}': ['p(95)<800', 'p(99)<2000'],
    'http_req_duration{endpoint:sync}': ['p(95)<1500', 'p(99)<3000'],
    'http_req_duration{endpoint:export_csv}': ['p(95)<2000'],
  },
};

function parsed(response) {
  try { return response.json(); } catch (_) { return null; }
}

function headers(token) { return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }; }
function tagged(token, endpoint) { return { headers: headers(token), tags: { endpoint } }; }
function fieldValues() {
  return Object.entries(values).map(([field_name, value]) => ({ field_name, field_value_json: JSON.stringify(value) }));
}
function record(participantId, marker) {
  return { project_id: PROJECT, template_id: TEMPLATE, participant_id: participantId,
    device_id: `loadtest-${marker}`, status: 'submitted', values: fieldValues() };
}
function mark(success) { flowFailures.add(!success); return success; }

export function setup() {
  let token = __ENV.ACCESS_TOKEN || '';
  if (!token) {
    required(__ENV.LOGIN_EMAIL && __ENV.LOGIN_PASSWORD, 'Indica ACCESS_TOKEN o LOGIN_EMAIL y LOGIN_PASSWORD de la cuenta de pruebas');
    const login = http.post(`${BASE}/api/v1/auth/login`, JSON.stringify({ email: __ENV.LOGIN_EMAIL, password: __ENV.LOGIN_PASSWORD }),
      { headers: { 'Content-Type': 'application/json' }, tags: { endpoint: 'login' } });
    required(login.status === 200 && parsed(login)?.access_token, `No fue posible iniciar sesion: HTTP ${login.status}`);
    token = parsed(login).access_token;
  }
  const template = http.get(`${BASE}/api/v1/runtime/template/${TEMPLATE}`, tagged(token, 'preflight_template'));
  required(template.status === 200 && parsed(template)?.template_id === TEMPLATE, `La cuenta no puede abrir la plantilla: HTTP ${template.status}`);
  const search = http.get(`${BASE}/api/v1/runtime/template/${TEMPLATE}/records/search?limit=1`, tagged(token, 'preflight_search'));
  required(search.status === 200 && Array.isArray(parsed(search)?.items), `La cuenta no puede buscar registros: HTTP ${search.status}`);
  return { token };
}

export function readFlow(data) {
  const offset = Math.floor(Math.random() * 5) * 25;
  const response = http.get(`${BASE}/api/v1/runtime/template/${TEMPLATE}/records/search?limit=25&offset=${offset}`,
    tagged(data.token, 'search'));
  const body = parsed(response);
  const success = response.status === 200 && Array.isArray(body?.items) && Number.isInteger(body?.total);
  check(response, { 'busqueda valida': () => success });
  mark(success);
  sleep(1);
}

export function captureFlow(data) {
  const index = exec.scenario.iterationInTest;
  const participantId = CAPTURE_IDS[index];
  required(participantId, `Falta participante de captura en indice ${index}`);
  const payload = record(participantId, `${RUN_ID}-capture-${SHARD_OFFSET + index}`);
  const response = http.post(`${BASE}/api/v1/runtime/save`, JSON.stringify(payload), tagged(data.token, 'capture'));
  const body = parsed(response);
  const success = response.status === 200 && Boolean(body?.id) && body.participant_id === participantId;
  check(response, { 'captura enlazada': () => success });
  mark(success);
  if (success) recordsCreated.add(1); else recordsFailed.add(1);
}

export function syncFlow(data) {
  const index = exec.scenario.iterationInTest;
  const ids = [];
  for (let position = index * BATCH_SIZE; position < Math.min((index + 1) * BATCH_SIZE, SYNC_IDS.length); position++) ids.push(SYNC_IDS[position]);
  required(ids.length > 0, `Falta lote de participantes en indice ${index}`);
  const key = `${RUN_ID}-sync-${SHARD_OFFSET + index}`;
  const payload = { project_id: PROJECT, template_id: TEMPLATE, idempotency_key: key, processing_mode: 'immediate',
    records: ids.map((id, position) => record(id, `${key}-${position}`)) };
  const response = http.post(`${BASE}/api/v1/runtime/session/bulk-save`, JSON.stringify(payload), tagged(data.token, 'sync'));
  const body = parsed(response);
  const success = response.status === 200 && body?.received === ids.length && body?.created === ids.length && body?.failed === 0
    && body?.replayed === false && Array.isArray(body?.results) && body.results.length === ids.length
    && body.results.every((item, position) => item.index === position && item.status === 'created' && item.id);
  check(response, { 'lote confirmado por registro': () => success });
  mark(success);
  if (success) recordsCreated.add(ids.length); else recordsFailed.add(body?.failed ?? ids.length);
  if (success && __ENV.VERIFY_REPLAY === 'true') {
    const replay = http.post(`${BASE}/api/v1/runtime/session/bulk-save`, JSON.stringify(payload), tagged(data.token, 'sync_replay'));
    const replayBody = parsed(replay);
    const replayOk = replay.status === 200 && replayBody?.replayed === true && replayBody?.job_id === body.job_id;
    check(replay, { 'reintento idempotente': () => replayOk });
    mark(replayOk);
  }
}

export function exportFlow(data) {
  const csv = http.get(`${BASE}/api/v1/runtime/template/${TEMPLATE}/records/export.csv`, tagged(data.token, 'export_csv'));
  const csvOk = csv.status === 200 && (csv.headers['Content-Type'] || '').includes('text/csv') && csv.body.length > 0;
  check(csv, { 'CSV descargado': () => csvOk });
  mark(csvOk);
  if (__ENV.ENABLE_XLSX === 'true' && __ITER % 6 === 0) {
    const xlsx = http.get(`${BASE}/api/v1/reports/project/${PROJECT}/summary.xlsx`, tagged(data.token, 'export_xlsx'));
    const xlsxOk = xlsx.status === 200 && (xlsx.headers['Content-Type'] || '').includes('spreadsheetml') && xlsx.body.length > 0;
    check(xlsx, { 'XLSX descargado': () => xlsxOk });
    mark(xlsxOk);
  }
  sleep(5);
}
