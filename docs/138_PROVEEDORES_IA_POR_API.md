# Proveedores de IA por API

El administrador configura las conexiones desde **Administración → Auditoría semántica con IA → Proveedores API**. Se pueden registrar varias conexiones por proyecto y elegir una de ellas al sugerir preguntas en el constructor. No se modifica el catálogo de 55 tipos de campo ni se publica un formulario automáticamente.

## Proveedores

Hay adaptadores para Google Gemini y Anthropic. OpenAI, OpenRouter, DeepSeek y Groq usan el mismo adaptador de chat completions compatible con OpenAI. **Otro compatible con OpenAI** permite una URL base HTTPS pública y el nombre exacto del modelo. La compatibilidad depende de que ese proveedor implemente `POST /chat/completions` con la estructura de respuesta esperada. No se promete compatibilidad con cualquier API arbitraria.

La lista de proveedores predefinidos evita escribir URLs a mano. Los modelos disponibles, límites y tarifas los define cada proveedor y pueden cambiar; el administrador indica el identificador del modelo habilitado en su cuenta.

## Seguridad y permisos

- `ai.audit.manage`: crear, editar, activar, desactivar y probar conexiones.
- `builder.write`: consultar la lista sin ver la clave y solicitar sugerencias para el formulario.
- La clave se guarda cifrada en `IntegrationSource.credentials_encrypted`; la respuesta de la API solo indica si existe. Una edición con clave vacía conserva la anterior.
- El constructor acepta únicamente conexiones activas del mismo proyecto. Las conexiones de IA están aisladas de los envíos a donantes.
- La prueba de conexión envía una solicitud mínima al proveedor. Puede consumir cuota o generar un cargo según la cuenta.
- Si hay varias conexiones activas, el constructor exige elegir una. La auditoría semántica conserva su configuración previa de variables de entorno `AI_AUDIT_*`; agregar una conexión para el constructor no cambia los flujos de aprobación.
- La opción de URL personalizada exige HTTPS público y rechaza direcciones privadas o locales.

## Estado y verificación

Se probaron permisos, cifrado, selección de conexión para el constructor y rechazo de URLs locales con una base aislada, sin llamadas pagas. También se ejecutaron las pruebas anteriores del módulo de auditoría y la compilación del frontend. La prueba real de cada proveedor requiere que el administrador registre una clave válida de su propia cuenta y pulse **Probar conexión**.

Documentación de los formatos: [Gemini](https://ai.google.dev/gemini-api/docs/api-key), [OpenRouter](https://openrouter.ai/docs/api/api-reference/chat/send-chat-completion-request), [Groq](https://console.groq.com/docs/api-reference), [DeepSeek](https://api-docs.deepseek.com/quick_start/pricing-details-cny/).
