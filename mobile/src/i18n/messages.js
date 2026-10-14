"use strict";

/**
 * Mensajes localizables del backend movil (docs/96 pendiente operativo #2).
 *
 * Estructura: { clave: { es: "...", en: "..." } }
 * El middleware i18n selecciona el idioma via Accept-Language y deja
 * `req.t(key, params?)` disponible para los controladores.
 */

const messages = {
  // Auth
  "auth.emailPasswordRequired":   { es: "Email y contraseña son requeridos",     en: "Email and password are required" },
  "auth.invalidCredentials":      { es: "Credenciales inválidas",                en: "Invalid credentials" },
  "auth.userNotFound":            { es: "Usuario no encontrado",                 en: "User not found" },
  "auth.refreshRequired":         { es: "Refresh token requerido",               en: "Refresh token required" },
  "auth.refreshInvalid":          { es: "Refresh token inválido o expirado",     en: "Invalid or expired refresh token" },
  "auth.loggedOut":               { es: "Sesión cerrada",                        en: "Logged out" },
  "auth.tokenInvalid":            { es: "Token inválido o expirado",             en: "Invalid or expired token" },
  "auth.accessDenied":            { es: "Acceso denegado",                       en: "Access denied" },

  // Registros
  "reg.notFound":                 { es: "Registro no encontrado",                en: "Record not found" },
  "reg.requiredFields":           { es: "Campos requeridos: plantilla_id, participante_id, respuestas", en: "Required fields: plantilla_id, participante_id, respuestas" },
  "reg.alreadySynced":            { es: "Registro ya sincronizado",              en: "Record already synced" },
  "reg.cannotDeleteSynced":       { es: "No se puede eliminar un registro ya sincronizado", en: "Cannot delete a synced record" },
  "reg.deleted":                  { es: "Registro eliminado",                    en: "Record deleted" },
  "reg.syncBatchRequired":        { es: "Se requiere un array de registros",     en: "An array of records is required" },

  // General
  "error.internal":               { es: "Error interno del servidor",            en: "Internal server error" },
  "error.fetchRecords":           { es: "Error al obtener registros",            en: "Error fetching records" },
  "error.fetchRecord":            { es: "Error al obtener registro",             en: "Error fetching record" },
  "error.createRecord":           { es: "Error al crear registro",               en: "Error creating record" },
  "error.updateRecord":           { es: "Error al actualizar registro",          en: "Error updating record" },
  "error.deleteRecord":           { es: "Error al eliminar registro",            en: "Error deleting record" },
  "error.syncBatch":              { es: "Error en sincronización batch",         en: "Batch sync error" },

  // Participantes
  "part.notFound":                { es: "Participante no encontrado",            en: "Participant not found" },
  "part.requiredFields":          { es: "Campos requeridos: nombre, tipo_documento, numero_documento", en: "Required fields: nombre, tipo_documento, numero_documento" },
  "part.duplicateDoc":            { es: "Ya existe un participante con ese documento", en: "A participant with that document already exists" },

  // Plantillas
  "tmpl.notFound":                { es: "Plantilla no encontrada",               en: "Template not found" },
};

const SUPPORTED_LANGS = ["es", "en"];
const DEFAULT_LANG = "es";

/**
 * Parsea Accept-Language y devuelve el primer idioma soportado, o el default.
 * Acepta ej. "en-US,en;q=0.9,es;q=0.8"
 */
function parseLang(header) {
  if (!header) return DEFAULT_LANG;
  const parts = header.split(",").map((p) => {
    const [tag, qStr] = p.trim().split(";q=");
    return { lang: tag.split("-")[0].toLowerCase(), q: qStr ? parseFloat(qStr) : 1 };
  });
  parts.sort((a, b) => b.q - a.q);
  for (const { lang } of parts) {
    if (SUPPORTED_LANGS.includes(lang)) return lang;
  }
  return DEFAULT_LANG;
}

/**
 * Express middleware: lee Accept-Language, expone req.lang y req.t(key).
 */
function i18nMiddleware(req, _res, next) {
  req.lang = parseLang(req.headers["accept-language"]);
  req.t = (key) => {
    const entry = messages[key];
    if (!entry) return key;
    return entry[req.lang] || entry[DEFAULT_LANG] || key;
  };
  next();
}

module.exports = { i18nMiddleware, messages, parseLang };
