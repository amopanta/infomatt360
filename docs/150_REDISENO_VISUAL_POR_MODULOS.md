# 150. Rediseño visual por módulos (2026-10-23)

Pedido del responsable: una interfaz menos simple, revisada módulo por módulo
y actividad por actividad. Este documento registra lo hecho en cada tanda.
Las capturas están en `docs/img/150/`.

## 1. Base común (todo el sistema)

- **Letra:** Atkinson Hyperlegible Next, empaquetada en la aplicación
  (`@fontsource-variable/atkinson-hyperlegible-next`), así que funciona sin
  conexión. Está pensada para leerse en pantallas pobres y con baja visión.
  El cero lleva una raya para no confundirlo con la «O» en cédulas y códigos.
- **Escala:** el texto base pasa de 12 px a 14 px.
- **Colores:** se mantiene el azul marino corporativo (`--navy: #0A2540`).
  Se agrega ocre (`--ochre`) para lo que espera acción, y un color por estado
  de registro (`.status-*`), igual en todas las pantallas.
- **Menú lateral:** los grupos dejan de ir en mayúsculas y la opción activa
  se marca con una barra a la izquierda.
- **Piezas comunes:** `.btn`, `.btn-primary`, `.data-table`, `.form-grid`,
  `.approval-badge`, `.module-page` y `.module-steps`. Varias pantallas
  usaban estas clases sin que existieran (por eso se veían sin estilo).
- **Estados en español:** en Inicio, Registros, Reportes y gráficos ya no
  aparecen «submitted», «paused» ni «published».

## 2. Inicio

- Cinta con el estado de los registros: cuántos están enviados, en revisión,
  devueltos o aprobados, en proporción (`components/StatusRibbon.tsx`).
- Tareas principales con iconos de línea en vez de emojis.
- Actividad reciente con fecha, autor y estado; columna de cifras del
  proyecto.

Capturas: `01-inicio-antes.png`, `02-inicio-despues.png`,
`05-inicio-celular.png`.

## 3. Registros

- Lista de formularios en filas comparables: nombre, respuestas, fecha y
  estado.
- Se corrigió el desborde horizontal de la pantalla.

Capturas: `03-registros-antes.png`, `04-registros-despues.png`.

## 4. Reportes

- Se quitó el bloque oscuro, que no coincidía con el resto del sistema y
  dejaba texto blanco sobre blanco en «Exportaciones guardadas».
- Pestañas claras (Resumen, Indicadores, Gráficos y tablas, Donantes, Mapa),
  sin símbolos.
- El resumen usa la misma cinta de estados de Inicio. La tabla por
  formulario muestra el estado traducido y una barra con el reparto.
- **Reportes con metas → «Empieza con un modelo»:**
  - *Avance por formulario:* un indicador por formulario publicado.
  - *Cobertura por municipio:* busca sola la pregunta de municipio.
  - *Informe de comité.*
  - *En blanco.*

  El modelo llena el reporte con los formularios del proyecto y la persona
  solo ajusta las metas.

Capturas: `06-reportes-antes.png`, `07-reportes-despues.png`,
`08-reportes-modelos.png`.

## 5. Funciones que existían pero no se veían

| Función | Dónde estaba | Qué pasaba | Ahora |
|---|---|---|---|
| Conexión con otras bases de datos (docs/146) | Avanzado → Base espejo (menú cerrado) | Pantalla sin estilos. La copia y la importación solo aparecían tras descubrir que el nombre de la base era un botón | **Datos → Bases de datos externas**, con pasos 1-2-3. Con una sola base conectada se abre directamente |
| Recorrido del gestor | Revisión → Equipos de campo, al final | Abría siempre en «hoy»: sin datos ese día, decía «No hay recorridos» | **Revisión → Recorridos y visitas**. Abre en el último día con actividad |
| Visitas a participantes | No existía en pantalla | — | Nuevo: lista y puntos en el mapa de cada formulario capturado ese día, con el participante y la ubicación GPS |

Servidor (nuevo, solo supervisión y administración):
- `GET /field-devices/project/{id}/route-days`: días con recorrido o con
  formularios capturados.
- `GET /field-devices/project/{id}/visits`: formularios del periodo con
  participante y primer punto GPS. Los que no tienen GPS se listan igual,
  sin punto en el mapa.
- Prueba: `tests/test_field_devices.py::test_route_days_and_visits_with_participant_and_gps`.

Capturas: `09-bases-externas-antes.png`, `10-bases-externas-despues.png`,
`11-recorridos-y-visitas.png`.

## 6. Segunda tanda: celular, Planeador, detalle de Registros, Participantes, Mapas y Equipos

- **Menú en celular:** arriba queda una barra con la marca y el botón
  «Menú». El menú se abre encima del contenido; antes ocupaba toda la
  pantalla antes de mostrar algo.
- **Estilo base de controles:** botones, campos, listas y enlaces sin estilo
  propio toman el del sistema (reglas con `:where()`, que no le ganan a
  ningún estilo de módulo). Esto arregla botones del navegador en
  Planeador, Participantes, Equipos y Llenar formularios.
- **Planeador:** márgenes de página, filtros en un recuadro y botones de
  arriba que ya no se salen de la pantalla.
- **Registros de un formulario:**
  - título con el nombre del formulario, número de registros y estado;
  - barra de herramientas ordenada;
  - iconos claros para «ver» y «editar» (antes ◉ y ✎);
  - estados con su color.
- **Participantes:** tipo y estado en español («Persona», «Activo»). La
  tabla se desplaza dentro de su recuadro en vez de cortarse.
- **Mapas:** encuadra todos los elementos (antes se centraba en el primero
  y los demás quedaban fuera de la vista). Los tipos salen en español
  (Punto, Trazado, Área).

Capturas: `12`–`20` (antes y después de Planeador, detalle de Registros,
Mapas y celular).

## 7. Tercera tanda: captura y constructor de formularios

**Captura (lo que llena el gestor):**
- El fondo del tema del formulario llega hasta abajo. Antes era una franja
  blanca cortada a media pantalla.
- **Datos del participante:** pasan de una tabla de una fila, que se cortaba
  en celular, a una ficha en rejilla. Tipo y estado salen en español; la
  «marca de duplicado» solo aparece cuando hay algo que advertir.
- Los botones Anterior y Siguiente se ven claros cuando están desactivados.
- «Borrador local activo.» pasa a decir: «Tus respuestas se guardan en este
  equipo mientras llenas el formulario.».

**Constructor:**
- La página tiene márgenes y las columnas laterales son más angostas, así
  que el lienzo tiene más espacio y los campos ya no se cortan.
- La casilla «Obligatorio» va en la misma línea que su texto.
- «Vista previa» y «Guardar plantilla» caben en una línea.
- **Iconos:** en el banco de preguntas y en el lienzo, los 53 emojis se
  reemplazan por iconos de línea, uno por categoría (`fieldLineIcon` en
  `fieldCatalog.ts`). Los emojis se veían distintos en cada equipo. En
  «¿Cómo quieres empezar?» pasa lo mismo.

Capturas: `21`–`27`.

## 8. Pruebas

- Backend: 559 pruebas.
- Web: 131 pruebas, incluida la de textos (`keys.test.ts`).
- Se revisó que no haya desborde horizontal en computador (1440 px) ni en
  celular (390 px).

## 9. Lo que sigue

- Manual de usuario con capturas del diseño nuevo.
