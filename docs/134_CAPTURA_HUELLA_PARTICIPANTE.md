# Captura de huella del participante: cámara y lector externo

## Estado

Diseño de integración. La verificación `FINGERPRINT` existente confirma al gestor mediante WebAuthn y no captura ni compara la huella del participante. No debe reutilizarse como prueba biométrica del participante.

## Experiencia de captura

El formulario debe ofrecer un campo independiente «Huella del participante» después de identificar y autorizar al participante. El administrador configura dos métodos permitidos: cámara del móvil y lector externo. El capturador elige uno de los métodos habilitados. Ambos producen una referencia al mismo participante y respuesta, con método, dispositivo, fecha, calidad y resultado. El registro no se marca como «identidad verificada» solo por adjuntar una imagen.

### Cámara del móvil

Mostrar una guía visual para ubicar los dedos, verificar foco e iluminación, tomar varias imágenes y pedir repetir cuando la calidad no alcance el umbral. Guardar la imagen aceptada como evidencia con acceso restringido. La generación de plantilla biométrica y su comparación posterior requieren un motor de captura sin contacto validado con los teléfonos reales. Hasta entonces, el sistema debe mostrar «evidencia capturada; comparación no disponible».

### Lector externo

La aplicación de escritorio o móvil usa un adaptador local del SDK del fabricante. El adaptador expone capacidades, captura, calidad y plantilla de comparación en un formato interno versionado; no acepta una afirmación de coincidencia enviada directamente por el navegador. La implementación del adaptador depende de marca, modelo, conexión y sistemas operativos del lector. Sin esos datos, la interfaz puede mostrar «lector no configurado», pero no debe ofrecer captura simulada.

La experiencia buscada es conectar, detectar y capturar sin configuraciones manuales cuando el lector esté soportado. La detección puede distinguir USB, HID y Bluetooth, pero el transporte por sí solo no define cómo obtener una huella: cada protocolo/SDK necesita un adaptador probado. Por eso el catálogo muestra «compatible», «detectado sin controlador» o «no detectado», y ofrece la cámara si no hay lector compatible. No se debe afirmar compatibilidad universal con cualquier marca o modelo.

## Asociación, acceso y recuperación

- Vincular toda captura a `project_id`, `template_id`, `record_id`, `participant_id`, `field_id` y usuario capturador; comprobar la asignación del usuario al participante y formulario también al leer o descargar.
- Cifrar los archivos biométricos y las plantillas, limitar su consulta a permisos específicos, auditar capturas, comparaciones, descargas y borrados. Definir consentimiento y conservación por proyecto antes de recolectar huellas reales.
- Mantener el identificador y la historia del participante cuando el gestor restablece la contraseña. La recuperación por correo y los códigos MFA existentes sirven para recuperar **la cuenta del gestor**; un código no sustituye una coincidencia biométrica del participante ni debe desbloquear datos sin autenticar y autorizar al usuario.
- Si se emplea cifrado de extremo a extremo con clave derivada únicamente de contraseña, diseñar previamente una clave de recuperación separada; de lo contrario, un restablecimiento de contraseña no podría descifrar la información antigua.

## Validación antes de producción

1. Probar cámara en los modelos Android/iPhone que usarán los gestores, incluida captura sin conexión y sincronización posterior.
2. Medir tasa de recaptura, falsos positivos y falsos negativos con participantes de prueba y los dedos definidos para el proyecto.
3. Integrar y probar el SDK del lector seleccionado; comparar un registro creado con cámara y otro con lector solo si el motor demuestra interoperabilidad.
4. Comprobar permisos de capturador, aprobador y administrador; recuperación de cuenta; bloqueo de registros aprobados; y exportaciones sin exposición de datos biométricos por defecto.

## Dependencia pendiente

Seleccionar y probar los primeros lectores para poblar el catálogo de compatibilidad (marca, modelo, conexión USB/Bluetooth y sistemas operativos). Confirmar también los modelos de teléfono para seleccionar y validar el motor de captura sin contacto. Se pueden añadir adaptadores de otros fabricantes sin cambiar el formulario ni los registros existentes.

### Primer catálogo de adaptadores propuesto

| Familia | Modelos iniciales | Escritorio | Móvil | Estado en InfoMatt360 |
| --- | --- | --- | --- | --- |
| HID DigitalPersona | 4500 y 5300 | SDK Windows disponible | SDK Android publicado; comprobar modelo y versión | Pendiente de licencia/SDK, equipo físico y pruebas |
| SecuGen | Hamster Pro 20 | SDK Windows disponible | SDK Android publicado; requiere conexión física compatible | Pendiente de SDK, equipo físico y pruebas |
| ZKTeco | SLK20R, ZK9500, ZK6500, ZK8500R | ZKFinger SDK Windows disponible | Sin compatibilidad móvil confirmada para estos modelos | Pendiente de SDK, equipo físico y pruebas |

Los perfiles de estas familias son candidatos, no lectores «compatibles» hasta completar una captura y una comparación real. Se debe probar **por separado** la aplicación de escritorio y la aplicación móvil; una captura que funcione en Windows no demuestra que funcione en Android o iPhone. Se prioriza Windows para escritorio y Android para campo. iPhone queda sujeto a disponibilidad explícita del SDK del fabricante y prueba del modelo. La conexión USB/Bluetooth y la compatibilidad de cada modelo se validan con el SDK y el equipo real; no se infieren del nombre comercial. Las familias no probadas siguen disponibles únicamente como opciones de planificación, nunca como captura activa.

Fuentes oficiales: [HID DigitalPersona SDK](https://sdk.hidglobal.com/node/34864), [SecuGen Hamster Pro 20](https://secugen.com/products/hamster-pro-20/), [ZKTeco ZKFinger SDK](https://www.zkteco.com/en/ZKFingerSDKforWindows).

