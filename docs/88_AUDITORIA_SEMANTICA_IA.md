# Auditoria semantica con IA

## Objetivo

Detectar automaticamente contradicciones o indicios de fraude en las
observaciones de campo (texto libre) que escribe un gestor territorial al
capturar un registro, usando un modelo de lenguaje (LLM) externo.

## Lo que dice la especificacion original

**4.8. Modulo de Auditoria Semantica con Inteligencia Artificial** —
"Analiza sintactica y semanticamente las cajas de texto de 'observaciones
de campo'... busca intencionadamente contradicciones humanas (ej. si el
gestor escribe *'el beneficiario manifiesta recibir conforme, pero
faltaron dos herramientas del kit'*)... provocando el rechazo automatico
del formulario en el peaje central."

## Decision de alcance: modo configurable, no solo rechazo automatico

El documento original solo describe rechazo automatico. En conversacion
con el usuario se acordo que la reaccion sea **configurable por
plantilla** via `AiAuditConfig.mode`:

| Modo | Comportamiento |
| --- | --- |
| `human` | Solo se guarda la alerta (`AiCheck`); un revisor humano decide si aprobar o rechazar. Ningun riesgo detectado cambia el estado del registro por si solo. |
| `automatic` | Cualquier riesgo detectado (`possible` o `high`) rechaza el registro automaticamente, sin intervencion humana -- el comportamiento literal del documento original. |
| `mixed` | Solo el riesgo `high` rechaza automaticamente; `possible` queda como alerta visible para que un humano decida (igual que `human` para ese caso). |

## Proveedores de LLM soportados

Multiples proveedores detras de un adaptador comun
(`backend/app/services/ai_audit_service.py`), configurables por variable
de entorno, inactivo por defecto (`AI_AUDIT_PROVIDER` vacio):

| `AI_AUDIT_PROVIDER` | Cubre | Variables adicionales |
| --- | --- | --- |
| `anthropic` | Claude (API nativa de Anthropic) | `AI_AUDIT_MODEL` (default `claude-sonnet-5`) |
| `openai_compatible` | OpenAI, **DeepSeek**, **Zhipu/GLM**, y cualquier otro proveedor que implemente el esquema de "chat completions" de OpenAI | `AI_AUDIT_BASE_URL` (ej. `https://api.deepseek.com/v1`), `AI_AUDIT_MODEL` (ej. `deepseek-chat`, `glm-4`) |
| `gemini` | Google Gemini | `AI_AUDIT_MODEL` (default `gemini-1.5-flash`) |

`AI_AUDIT_API_KEY` es obligatoria para cualquier proveedor. Sin
`AI_AUDIT_PROVIDER` configurado, el analisis se registra con
`status="skipped"` y el guardado del registro funciona exactamente igual
que sin este modulo.

`openai_compatible` es la pieza clave para "todos los proveedores": en vez
de escribir un cliente por cada plataforma, se aprovecha que OpenAI,
DeepSeek, Zhipu/GLM y varios mas ya exponen el mismo formato de API
(`POST {base_url}/chat/completions`) -- cambiar de uno a otro es solo
cambiar `AI_AUDIT_BASE_URL`, `AI_AUDIT_MODEL` y la API key.

## Disparador: al guardar el registro, no al aprobarlo

A diferencia de ERP y la interoperabilidad con donantes (disparados al
**aprobar**), la auditoria semantica se dispara en
`runtime_record_service.save_record()`, justo **despues** de que el
registro ya quedo guardado (commit + refresh), nunca antes: la captura de
datos en campo no debe perderse ni demorarse por una llamada a un
servicio de IA externo lento o caido. Si `AiAuditConfig` no existe para la
plantilla, o el campo de texto configurado esta vacio, no hace nada.

## Modelo

- `AiAuditConfig` (`backend/app/models/ai.py`): `template_id` (unico),
  `text_field_name` (que campo del formulario auditar), `mode`.
- Los resultados reutilizan `AiCheck` (ya existia, antes sin
  comportamiento real): `check_type="semantic_audit"`, `status` = el
  `risk_level` devuelto (`none`/`possible`/`high`) o `skipped`/`error`,
  `result_json` con el razonamiento y las frases senaladas por el modelo.

## Prompt y parseo de la respuesta

El prompt (ver `PROMPT_TEMPLATE` en `ai_audit_service.py`) pide
explicitamente al modelo responder **solo** con un JSON
`{"risk_level": "...", "reasoning": "...", "flagged_phrases": [...]}`. El
parseo primero intenta `json.loads()` directo; si el modelo agrego texto
alrededor del JSON, se extrae el primer bloque `{...}` con una expresion
regular antes de fallar. Un `risk_level` fuera de `none`/`possible`/`high`
o una respuesta no parseable se trata como `status="error"`.

## Endpoints (`backend/app/api/v1/ai_audit.py`, prefijo `/api/v1/ai-audit`)

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/config` | `ai.audit.manage` |
| `GET` | `/config/{template_id}` | acceso al proyecto |
| `POST` | `/records/{record_id}/analyze` | `ai.audit.manage` (reanalisis manual, ej. si la config se agrego despues de capturado el registro) |

Los resultados (`AiCheck`) se consultan con el endpoint ya existente
`GET /api/v1/ai/checks/{project_id}`.

## Como activarlo

1. Consigue una API key del proveedor elegido (Anthropic, OpenAI, DeepSeek,
   Zhipu/GLM o Gemini).
2. Configura en `backend/.env`: `AI_AUDIT_PROVIDER`, `AI_AUDIT_API_KEY`, y
   si aplica `AI_AUDIT_BASE_URL`/`AI_AUDIT_MODEL`.
3. `POST /ai-audit/config` con el `template_id` del formulario y el
   `text_field_name` a auditar.

## Limites conocidos

- Sin pantalla propia en el frontend todavia (se opera por Swagger/API directa).
- La llamada al LLM es sincrona dentro de la peticion de guardado: en un
  formulario con auditoria activa, guardar un registro tarda lo que tarde
  el proveedor de IA en responder (con timeout de 20s). No hay cola en
  segundo plano para esto en el alcance actual.
- Un solo campo de texto por plantilla; no analiza multiples campos ni
  combina evidencias de varios campos a la vez.
