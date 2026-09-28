# Validación del ERP de InfoMatt360

Fecha: 28 de septiembre de 2026. Entorno: VPS de producción, `https://infomatt360.tecnomatt.com`, código `d891291`.

## Resultado

El módulo implementado corresponde al alcance descrito en `docs/84_ERP_HEADLESS_INVENTARIO_NOMINA.md`: inventario por SKU y proyecto, descuento al aprobar entregas de formularios vinculados, historial de movimientos y honorarios de tarifa fija. **Siete pruebas específicas pasaron** en un contenedor aislado que usa el código del VPS. La API de salud respondió `200`; inventario y honorarios rechazaron solicitudes sin sesión con `401`.

La base de producción contiene **0 ítems, 0 movimientos, 0 honorarios y 0 configuraciones de formulario ERP**. Por ello no existe aún un flujo ERP real para certificar en producción. Esta revisión no creó ni modificó datos de negocio y no dispuso de una sesión autenticada para comprobar la interfaz por rol.

| Requisito documentado | Evidencia | Estado |
| --- | --- | --- |
| Crear ítem y movimiento de alta inicial | Prueba `test_create_inventory_item...` en `backend/tests/test_erp.py` | Aprobado en entorno aislado |
| Impedir SKU duplicado por proyecto | Prueba de respuesta `409` | Aprobado en entorno aislado |
| Descontar stock y acreditar honorario al aprobar | Prueba de aprobación con movimiento y honorario | Aprobado en entorno aislado |
| Rechazar aprobación por stock insuficiente sin liquidar | Prueba de error y saldos sin cambio | Aprobado en entorno aislado |
| No liquidar formularios sin configuración ERP | Prueba de formulario no vinculado | Aprobado en entorno aislado |
| Restringir gestión y acceso por proyecto | Pruebas de permisos y consultas; ruta pública sin sesión `401` | Aprobado en API aislada y barrera pública |
| Marcar honorario como pagado y rechazar doble marcado | Prueba de actualización y segundo intento `409` | Aprobado en entorno aislado |
| Uso completo desde la interfaz con usuarios reales de prueba | Sin sesión autenticada y sin configuración ERP en producción | Pendiente |

## Hallazgos funcionales

1. El módulo es deliberadamente limitado. No incluye compras, reposiciones posteriores al alta, varias bodegas, facturación, impuestos, contabilidad general, nómina legal ni desembolsos bancarios.
2. La vinculación exige escribir el ID de plantilla y los nombres internos exactos de los campos. El sistema no verifica esos nombres al crear la configuración.
3. La interfaz no ofrece edición de una configuración ERP ni reversión de una liquidación aprobada. Una corrección posterior del registro puede dejar inventario y honorarios desalineados si se trata como reversión.
4. La pantalla de Honorarios filtra por `user_id`, no por nombre; esto dificulta el uso por personal operativo.
5. El Excel adjunto es una **plantilla de preparación y validación**, con una fila de ejemplo ficticia. El módulo no dispone de importación masiva de esa plantilla.

## Siguiente validación en producción

Con una cuenta de pruebas que tenga permisos de gestión ERP y otra de aprobación, crear un proyecto o caso QA aislado; cargar un SKU de prueba con 10 unidades; vincular un formulario de entrega con campos SKU y cantidad; enviar y aprobar una respuesta de 3 unidades; comprobar saldo 7, movimiento `-3` y honorario acumulado. Después intentar una entrega de 99 unidades, confirmar que la aprobación se rechaza sin cambiar saldos, y registrar el resultado en la pestaña **Validación** del Excel. El marcado de pago se debe probar solo con un honorario de prueba.

## Entregables

- `plantilla-erp-infomatt360.xlsx`: hojas Guía, Inventario, Vinculaciones y Validación.
- `manual-usuario-erp-infomatt360.docx`: pasos de uso, errores frecuentes y límites actuales.
