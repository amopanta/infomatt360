# Equipos múltiples y perfiles de seguimiento

## Estado implementado

- La pantalla **Equipos de gestores** permite buscar equipos por nombre; la búsqueda de integrantes por nombre, correo, documento o código ya existía.
- Un formulario puede usar varios equipos como fuente de participantes. La población elegible es la unión de los integrantes de esos equipos y cada participante aparece una sola vez. La configuración anterior de un solo equipo sigue siendo válida.
- La asignación de un participante a un responsable sigue siendo explícita. Pertenecer a un equipo no otorga acceso automático al formulario o a sus registros.
- Varios usuarios pueden tener rol administrador dentro de un mismo proyecto mediante asignaciones independientes. Actualmente, ese permiso es del proyecto, no de un formulario individual.

## Perfiles recomendados

| Perfil | Alcance | Facultades sugeridas |
| --- | --- | --- |
| Administrador de proyecto | Proyecto completo | Configurar formularios, equipos, permisos y responsables. Puede haber varios. |
| Administrador de formulario | Formularios seleccionados | Gestionar publicación, fuentes, asignaciones y administradores de esos formularios; sin administrar otros. |
| Supervisor nacional | Organización o proyectos seleccionados | Consultar indicadores, formularios y gestores de su ámbito, sin editar respuestas. |
| Supervisor regional | Regiones, departamentos y formularios seleccionados | Seguimiento y reportes limitados a ese alcance. |
| Supervisor departamental | Departamentos, municipios y formularios seleccionados | Seguimiento de los gestores y participantes de su territorio. |
| Supervisor de equipo | Equipos y formularios seleccionados | Consultar el avance de los gestores de esos equipos y sus registros autorizados. |

## Reglas para implementar el alcance granular

El rol define **qué acción** se permite; una asignación de alcance define **sobre qué datos**. Un usuario podría tener varios formularios, equipos y territorios simultáneamente. La consulta efectiva debe ser la intersección de los formularios autorizados con el territorio y equipos autorizados; varios valores de una misma dimensión se unen sin duplicar registros. Los filtros deben aplicarse en las API de participantes, registros, reportes y exportaciones, no solamente en la interfaz. Toda modificación del alcance debe auditarse.

Los perfiles por formulario, equipo y territorio combinados quedan como desarrollo pendiente. Los permisos actuales de administrador de proyecto y las restricciones territoriales existentes no equivalen todavía a ese control granular de seguimiento.

