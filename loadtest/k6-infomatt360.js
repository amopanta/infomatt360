// Script de prueba de carga para InfoMatt360 (auditoria tecnica externa
// julio 2026, docs/119). Genera la evidencia real de carga que la auditoria
// pedia y que hasta ahora no existia -- ver docs/108.
//
// Uso basico (contra un entorno real, nunca contra datos de produccion sin
// avisar al responsable -- ver loadtest/README.md):
//
//   k6 run -e BASE_URL=https://api.tu-dominio.com \
//           -e LOGIN_EMAIL=... -e LOGIN_PASSWORD=... \
//           -e PROJECT_ID=... -e TEMPLATE_ID=... \
//           -e TARGET_VUS=3000 -e SUSTAIN_DURATION=10m \
//           loadtest/k6-infomatt360.js
//
// Por defecto corre a escala minima (5 VUs, 30s) para no disparar nada
// grande por accidente -- hay que subir TARGET_VUS/SUSTAIN_DURATION a
// proposito para generar evidencia real de 3.000 usuarios.

import http from 'k6/http';
import { check, sleep } from 'k6';

const BASE_URL = (__ENV.BASE_URL || 'http://localhost:8000').replace(/\/$/, '');
const LOGIN_EMAIL = __ENV.LOGIN_EMAIL || 'admin@infomatt360.demo';
const LOGIN_PASSWORD = __ENV.LOGIN_PASSWORD || 'Demo12345!';
const PROJECT_ID = __ENV.PROJECT_ID || 'demo-project-infomatt360';
const TEMPLATE_ID = __ENV.TEMPLATE_ID || 'demo-template-characterization';
const ENABLE_WRITES = (__ENV.ENABLE_WRITES || 'false').toLowerCase() === 'true';

const TARGET_VUS = Number(__ENV.TARGET_VUS || 5);
const WRITE_TARGET_VUS = Number(__ENV.WRITE_TARGET_VUS || Math.max(1, Math.floor(TARGET_VUS / 5)));
const RAMP_DURATION = __ENV.RAMP_DURATION || '30s';
const SUSTAIN_DURATION = __ENV.SUSTAIN_DURATION || '30s';

// Marcador real en los datos escritos para poder ubicarlos y borrarlos
// despues -- nunca se disfraza de dato real.
const WRITE_MARKER = 'k6-load-test';

const scenarios = {
  read_traffic: {
    executor: 'ramping-vus',
    exec: 'readScenario',
    startVUs: 0,
    stages: [
      { duration: RAMP_DURATION, target: TARGET_VUS },
      { duration: SUSTAIN_DURATION, target: TARGET_VUS },
      { duration: RAMP_DURATION, target: 0 },
    ],
  },
};

if (ENABLE_WRITES) {
  scenarios.write_traffic = {
    executor: 'ramping-vus',
    exec: 'writeScenario',
    startVUs: 0,
    stages: [
      { duration: RAMP_DURATION, target: WRITE_TARGET_VUS },
      { duration: SUSTAIN_DURATION, target: WRITE_TARGET_VUS },
      { duration: RAMP_DURATION, target: 0 },
    ],
  };
}

export const options = {
  scenarios,
  thresholds: {
    http_req_failed: ['rate<0.01'],
    'http_req_duration{endpoint:health}': ['p(95)<200'],
    'http_req_duration{endpoint:search}': ['p(95)<500', 'p(99)<1500'],
    'http_req_duration{endpoint:save}': ['p(95)<800', 'p(99)<2000'],
  },
};

// Login una sola vez en setup(), no en cada iteracion -- 3.000 usuarios
// concurrentes usando la app ya autenticada es lo que la auditoria pide
// evidenciar, no 3.000 intentos de login por segundo (que ademas chocaria
// casi de inmediato contra el throttle real de login: 25 intentos por IP
// cada 15 minutos, ver app/api/v1/auth.py).
export function setup() {
  const res = http.post(
    `${BASE_URL}/api/v1/auth/login`,
    JSON.stringify({ email: LOGIN_EMAIL, password: LOGIN_PASSWORD }),
    { headers: { 'Content-Type': 'application/json' }, tags: { endpoint: 'login' } },
  );
  const ok = check(res, { 'login devolvio 200': (r) => r.status === 200 });
  if (!ok) {
    throw new Error(`No fue posible autenticar contra ${BASE_URL}: HTTP ${res.status} ${res.body}`);
  }
  return { token: res.json('access_token') };
}

function authHeaders(token) {
  return { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' };
}

export function readScenario(data) {
  const headers = authHeaders(data.token);

  const health = http.get(`${BASE_URL}/api/v1/health/ready`, { tags: { endpoint: 'health' } });
  check(health, { 'health ready': (r) => r.status === 200 });

  const offset = Math.floor(Math.random() * 5) * 25;
  const search = http.get(
    `${BASE_URL}/api/v1/runtime/template/${TEMPLATE_ID}/records/search?limit=25&offset=${offset}`,
    { headers, tags: { endpoint: 'search' } },
  );
  check(search, { 'search devolvio 200': (r) => r.status === 200 });

  sleep(1);
}

export function writeScenario(data) {
  const headers = authHeaders(data.token);
  const marker = `${WRITE_MARKER}-vu${__VU}-iter${__ITER}-${Date.now()}`;

  const payload = JSON.stringify({
    project_id: PROJECT_ID,
    template_id: TEMPLATE_ID,
    status: 'submitted',
    values: [
      { field_name: 'nombre', field_value_json: JSON.stringify(marker) },
      { field_name: 'integrantes', field_value_json: JSON.stringify(1 + (__ITER % 5)) },
      { field_name: 'observaciones', field_value_json: JSON.stringify(`Registro generado por loadtest/k6-infomatt360.js (${WRITE_MARKER}) -- seguro de borrar.`) },
    ],
  });

  const res = http.post(`${BASE_URL}/api/v1/runtime/save`, payload, { headers, tags: { endpoint: 'save' } });
  check(res, { 'save devolvio 200': (r) => r.status === 200 });

  sleep(1);
}
