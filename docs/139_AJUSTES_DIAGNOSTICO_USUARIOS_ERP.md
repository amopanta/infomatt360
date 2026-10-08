# Ajustes a partir del diagnóstico de InfoMatt360

## Alcance implementado

Se amplía `/admin/users` como **Usuarios y permisos**: crear cuentas con rol por proyecto, crear roles a partir de los permisos concedibles, consultar permisos efectivos e identificar los heredados de organización, cambiar rol y suspender/reactivar la asignación al proyecto. No se modifica el estado global de la identidad ni se edita un rol compartido por otros proyectos.

La creación y los cambios de acceso requieren reautenticación administrativa y generan auditoría sin contraseñas. Las contraseñas temporales son aleatorias y exigen cambio al iniciar sesión. La API antigua de creación deja de usar `ChangeMe123`; debe usarse el nuevo flujo administrativo para obtener una contraseña temporal, o recuperación de cuenta para identidades creadas mediante la API antigua.

La asignación antigua verifica permisos en el proyecto solicitado, rechaza roles superiores y asignaciones duplicadas; su listado filtra al ámbito administrable. Los cambios de correo, contraseña y MFA comprueban todas las asignaciones activas de la identidad, porque afectan también sus otros proyectos. Una cuenta con acceso heredado por organización no puede considerarse suspendida desde un solo proyecto: se rechaza esa operación y se indica revisar su asignación de organización.

Las renovaciones simultáneas de sesión dentro de una misma página comparten una solicitud, evitando reutilizar una cookie rotatoria por montajes o solicitudes concurrentes. Esto no demuestra la causa del corte de sesión observado y no sincroniza renovaciones entre pestañas.

Registros muestra nombres de capturadores, estados en español y fechas operativas en `America/Bogota`, interpretando las fechas sin zona del servidor como UTC. ERP muestra nombres de gestores y razones de movimientos traducidas. Los honorarios revertidos se distinguen de los pagados y la API impide marcarlos como pagados.

## ERP: ejemplo de operación

1. Crear inventario `KIT-EJEMPLO`, cantidad 10, en un proyecto de pruebas.
2. Configurar una plantilla publicada: campo SKU `sku_kit`, cantidad `cantidad_entregada`, honorario 15000.
3. Capturar una entrega de 3 unidades y aprobar el registro: existencias 7 y honorario causado 15000 para el capturador.
4. Reabrir para corrección antes de pagar: se devuelve el inventario y se revierte el honorario anterior.
5. Corregir a 2 unidades y aprobar nuevamente: existencias 8 y un nuevo honorario vigente. El anterior permanece revertido y no puede pagarse.
6. Marcar pagado únicamente un honorario vigente tras verificar el pago real. Este cambio no ejecuta una transferencia bancaria.

El Excel existente prepara/valida plantillas; este ajuste no añade importación directa de inventario.

## Validación y publicación

Ejecutar en backend `python -m pytest -q`, en frontend `npm test` y `npm run build`. Se agregaron pruebas de credenciales únicas, duplicados, reautenticación, aislamiento, bloqueo de escalamiento, invalidación de caché, acceso heredado, protección de cuentas con otros proyectos, renovación concurrente y zona horaria. La regresión ERP cubre descuento, reversión, reaprobación y rechazo de pago de honorarios revertidos.

No requiere cambios de esquema. Backend y frontend deben publicarse juntos. Antes del despliegue: confirmar la versión instalada y su configuración, generar respaldo recuperable y usar el procedimiento habitual del VPS. Tras publicar, validar con perfiles administrador, capturador, revisor, coordinador y consulta; repetir también con otro proyecto y con un administrador de organización.

Pendiente: publicación y comprobación en el VPS, pruebas manuales de todos los módulos pendientes en el diagnóstico, vinculación de identidades ya existentes mediante una interfaz, mantenimiento de asignaciones de organización, pruebas de carga, renovación entre pestañas y revisión completa de las API administrativas globales. El catálogo de roles existente es global: aquí solo se crean roles nuevos; no se editan los compartidos. No se certifica el funcionamiento completo del producto con estas pruebas locales.

### Resultado local de esta entrega

- Backend: **498 pruebas correctas**, suite completa, sin fallos (327 segundos).
- Frontend: **110 pruebas correctas** en 24 archivos; compilación TypeScript/Vite/PWA correcta.
- Se preparó el directorio local de archivos requerido por las pruebas de disponibilidad. Los administradores de las pruebas de asignación ahora tienen explícitamente los permisos que conceden; las pruebas negativas impiden conceder permisos superiores.
- Persisten avisos de dependencias obsoletas y de tamaño del paquete frontend; no equivalen a fallos de estas pruebas.
- Cambios guardados localmente; envío a GitHub bloqueado por revisión automática por falta de autorización explícita del destino. Sin despliegue al VPS ni verificación manual de la nueva interfaz en producción.
