/**
 * Proyecto: InfoMatt360
 * Modulo: Builder Default Template
 * Responsabilidad: Crear una plantilla inicial de caracterizacion para pruebas del MVP.
 */

import { createColumn, createComponent, createPage, createRow, createSection, createTemplate } from './api';

export async function createDefaultCharacterizationTemplate(projectId: string) {
  const template = await createTemplate({ projectId, name: 'Caracterizacion de Hogares', description: 'Plantilla inicial MVP' });
  const page = await createPage({ templateId: template.id, title: 'Informacion General' });
  const section = await createSection({ pageId: page.id, title: 'Datos Basicos' });
  const row1 = await createRow({ sectionId: section.id, sortOrder: 1 });
  const col1 = await createColumn({ rowId: row1.id, desktopWidth: 6, sortOrder: 1 });
  const col2 = await createColumn({ rowId: row1.id, desktopWidth: 6, sortOrder: 2 });
  await createComponent({ templateId: template.id, columnId: col1.id, type: 'TEXT', name: 'nombre_completo', label: 'Nombre completo', sortOrder: 1 });
  await createComponent({ templateId: template.id, columnId: col2.id, type: 'TEXT', name: 'documento', label: 'Documento', sortOrder: 2 });
  const row2 = await createRow({ sectionId: section.id, sortOrder: 2 });
  const col3 = await createColumn({ rowId: row2.id, desktopWidth: 6, sortOrder: 1 });
  const col4 = await createColumn({ rowId: row2.id, desktopWidth: 6, sortOrder: 2 });
  await createComponent({ templateId: template.id, columnId: col3.id, type: 'TEXT', name: 'municipio', label: 'Municipio', sortOrder: 3 });
  await createComponent({ templateId: template.id, columnId: col4.id, type: 'TEXT', name: 'celular', label: 'Celular', sortOrder: 4 });
  return template;
}
