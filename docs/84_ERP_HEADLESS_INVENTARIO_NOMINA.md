# ERP headless: inventario y honorarios (liquidacion transaccional)

## Objetivo

Motor contable minimo, no un ERP de proposito general. Reemplaza la
dependencia de sistemas externos (Odoo) para un caso de uso especifico:
cuando un registro de formulario que representa una entrega de insumos
llega a estado "Aprobado", el sistema descuenta el stock del insumo
entregado y acredita un honorario de tarifa plana al gestor que hizo la
entrega, en una sola operacion atomica. Ver el alcance minimo acordado y lo
explicitamente descartado (contabilidad general, facturacion, impuestos,
nomina real, compras, multiples bodegas, desembolso bancario) en la
conversacion de diseno que origino este modulo.

## Modelos (`backend/app/models/erp.py`)

- `ErpTemplateConfig` — vincula una plantilla del Builder al motor ERP:
  `template_id` (unico), `sku_field_name`, `quantity_field_name` (nombres
  de campo del formulario donde estan el SKU y la cantidad entregada),
  `fee_amount` (tarifa plana por registro aprobado). Una plantilla sin fila
  aqui no dispara ninguna liquidacion — la mayoria de formularios no
  representan una entrega.
- `ErpInventoryItem` — saldo actual de un SKU en la bodega regional de un
  proyecto (una sola bodega por proyecto, sin subbodegas).
- `ErpInventoryMovement` — ledger inmutable de movimientos de inventario
  (nunca se edita/borra una fila; cada ajuste es una fila nueva).
- `ErpPayrollEntry` — ledger inmutable de honorarios acumulados por
  gestor, `status` `accrued` (generado automaticamente) o `paid` (marcado
  manualmente, sin desembolso bancario real).

## Disparador: aprobacion de un registro

El enganche vive en `review_service.apply_action()`
(`backend/app/services/review_service.py`), justo despues de fijar
`record.status = payload.to_status` y antes de `db.commit()`:

```python
if isinstance(record, RuntimeRecord) and payload.to_status == "approved":
    erp_service.settle_record(db, record)
```

`erp_service.settle_record()` (`backend/app/services/erp_service.py`):

1. Busca `ErpTemplateConfig` por `record.template_id`. Si no existe, no
   hace nada (no-op silencioso).
2. Lee los valores del registro (`RuntimeRecordValue`) para los campos
   configurados como SKU y cantidad.
3. Busca el `ErpInventoryItem` por `(project_id, sku)`.
4. Si el stock disponible es menor a la cantidad solicitada, **lanza
   `ValueError`** con el detalle del faltante.
5. Si hay stock suficiente, descuenta `quantity_on_hand`, inserta la fila
   de `ErpInventoryMovement`, y acredita un `ErpPayrollEntry` al
   `record.submitted_by` (el gestor que capturo el registro) por el
   `fee_amount` configurado.

## Por que el bloqueo de stock revierte tambien el cambio de estado

`settle_record()` se llama *antes* del unico `db.commit()` de
`apply_action()`. La sesion de SQLAlchemy no aplica ningun cambio
(`record.status`, la fila de `ReviewAction`, la de `RecordEvent`) hasta ese
commit; si `settle_record()` lanza `ValueError`, la excepcion se propaga sin
que nada se haya confirmado, y `get_db()` simplemente cierra la sesion sin
comitear (`backend/app/db/session.py`). El endpoint
(`backend/app/api/v1/review.py`) captura el `ValueError` y responde
`400 Bad Request` con el detalle. El registro queda exactamente en su
estado anterior — el mismo efecto que el ROLLBACK ACID descrito en la
especificacion original, logrado con la semantica normal de una
transaccion de SQLAlchemy en vez de una transaccion explicita separada.

## Endpoints (`backend/app/api/v1/erp.py`, prefijo `/api/v1/erp`)

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/template-config` | `erp.manage` (validado contra el proyecto de la plantilla) |
| `GET` | `/template-config/{template_id}` | acceso al proyecto de la plantilla |
| `POST` | `/inventory` | `erp.manage` |
| `GET` | `/inventory/project/{project_id}` | acceso al proyecto |
| `GET` | `/inventory/{item_id}/movements` | acceso al proyecto del item |
| `GET` | `/payroll/project/{project_id}?gestor_user_id=...` | acceso al proyecto |
| `PATCH` | `/payroll/{entry_id}/mark-paid` | `erp.manage` |

`POST /inventory` con `quantity_on_hand` inicial mayor a cero genera
tambien una fila de movimiento (`reason="alta_inicial"`) para que el
ledger sea completo desde el primer registro del item.

## Limites conocidos

- Sin pantalla propia en el frontend todavia (se opera por Swagger/API
  directa, igual que Excel import y backups).
- No hay endpoint para deshacer una liquidacion ya aplicada (ej. si un
  registro aprobado se revierte despues) — el ledger de movimientos
  permite auditar que paso, pero la reversion manual del stock/honorario
  quedaria fuera de este alcance minimo.
- `sku_field_name`/`quantity_field_name` deben coincidir exactamente con el
  `field_name` real del componente en el Builder; no hay validacion
  cruzada al crear el `ErpTemplateConfig` que confirme que esos campos
  existen en la plantilla.
