const { db } = require('../models/database');

exports.resumen = (req, res) => {
  try {
    const { desde, hasta, proyecto_id } = req.query;
    const userId = req.user.id;

    let dateFilter = '';
    const params = [userId];
    if (desde) { dateFilter += ` AND r.created_at >= ?`; params.push(desde); }
    if (hasta) { dateFilter += ` AND r.created_at <= ?`; params.push(hasta + 'T23:59:59'); }

    // Totales
    const totales = db.prepare(`
      SELECT
        COUNT(*) as total_registros,
        SUM(CASE WHEN estado = 'sincronizado' THEN 1 ELSE 0 END) as sincronizados,
        SUM(CASE WHEN estado = 'completado' THEN 1 ELSE 0 END) as completados,
        SUM(CASE WHEN estado = 'borrador' THEN 1 ELSE 0 END) as borradores,
        SUM(CASE WHEN estado = 'error' THEN 1 ELSE 0 END) as errores,
        SUM(tiene_huella) as con_huella,
        SUM(tiene_firma) as con_firma
      FROM registros r WHERE r.usuario_id = ? ${dateFilter}
    `).get(...params);

    // Tasa de envío
    const tasaEnvio = totales.total_registros > 0
      ? ((totales.sincronizados / totales.total_registros) * 100).toFixed(1)
      : 0;

    // Por día de la semana
    const porDia = db.prepare(`
      SELECT
        CASE cast(strftime('%w', r.created_at) as integer)
          WHEN 0 THEN 'Dom' WHEN 1 THEN 'Lun' WHEN 2 THEN 'Mar'
          WHEN 3 THEN 'Mie' WHEN 4 THEN 'Jue' WHEN 5 THEN 'Vie' WHEN 6 THEN 'Sab'
        END as dia,
        COUNT(*) as total,
        SUM(CASE WHEN estado = 'sincronizado' THEN 1 ELSE 0 END) as sincronizados,
        SUM(CASE WHEN estado != 'sincronizado' THEN 1 ELSE 0 END) as pendientes
      FROM registros r WHERE r.usuario_id = ? ${dateFilter}
      GROUP BY strftime('%w', r.created_at)
      ORDER BY cast(strftime('%w', r.created_at) as integer)
    `).all(...params);

    // Por hora
    const porHora = db.prepare(`
      SELECT cast(strftime('%H', r.created_at) as integer) as hora, COUNT(*) as total
      FROM registros r WHERE r.usuario_id = ? ${dateFilter}
      GROUP BY hora ORDER BY hora
    `).all(...params);

    // Por plantilla
    const porPlantilla = db.prepare(`
      SELECT pl.nombre, COUNT(*) as total,
        SUM(CASE WHEN r.estado = 'sincronizado' THEN 1 ELSE 0 END) as sincronizados
      FROM registros r
      JOIN plantillas pl ON r.plantilla_id = pl.id
      WHERE r.usuario_id = ? ${dateFilter}
      GROUP BY pl.id ORDER BY total DESC
    `).all(...params);

    // Cobertura de participantes
    const totalParticipantes = db.prepare(`
      SELECT COUNT(DISTINCT p.id) as total
      FROM participantes p
      JOIN proyectos pr ON p.proyecto_id = pr.id
      JOIN usuario_proyecto up ON pr.id = up.proyecto_id
      WHERE up.usuario_id = ?
    `).get(userId).total;

    const participantesConRegistro = db.prepare(`
      SELECT COUNT(DISTINCT r.participante_id) as total
      FROM registros r WHERE r.usuario_id = ? ${dateFilter}
    `).get(...params).total;

    // Promedio diario
    let promedioDiario = 0;
    if (desde && hasta) {
      const dias = Math.max(1, Math.ceil((new Date(hasta) - new Date(desde)) / 86400000));
      promedioDiario = (totales.total_registros / dias).toFixed(1);
    }

    // Tiempo promedio entre registros
    const tiempoPromedio = db.prepare(`
      SELECT AVG(diff) as promedio FROM (
        SELECT julianday(r.created_at) - julianday(LAG(r.created_at) OVER (ORDER BY r.created_at)) as diff
        FROM registros r WHERE r.usuario_id = ? ${dateFilter}
      ) WHERE diff IS NOT NULL AND diff < 1
    `).get(...params);

    res.json({
      totales,
      tasa_envio: Number(tasaEnvio),
      cobertura: {
        total_participantes: totalParticipantes,
        con_registro: participantesConRegistro,
        porcentaje: totalParticipantes > 0 ? ((participantesConRegistro / totalParticipantes) * 100).toFixed(1) : 0,
      },
      promedio_diario: Number(promedioDiario),
      tiempo_promedio_horas: tiempoPromedio?.promedio ? (tiempoPromedio.promedio * 24).toFixed(1) : null,
      actividad_diaria: porDia,
      actividad_horaria: porHora,
      por_plantilla: porPlantilla,
    });
  } catch (err) {
    console.error('Stats error:', err);
    res.status(500).json({ error: 'Error al obtener estadísticas' });
  }
};

exports.exportar = (req, res) => {
  try {
    const { formato = 'json', desde, hasta } = req.query;
    let dateFilter = '';
    const params = [req.user.id];
    if (desde) { dateFilter += ` AND r.created_at >= ?`; params.push(desde); }
    if (hasta) { dateFilter += ` AND r.created_at <= ?`; params.push(hasta + 'T23:59:59'); }

    const registros = db.prepare(`
      SELECT r.id, r.estado, r.created_at, r.synced_at, r.latitud, r.longitud,
        r.tiene_huella, r.tiene_firma, r.respuestas_json,
        pl.nombre as formulario, pa.nombre as participante, pa.numero_documento, pa.codigo
      FROM registros r
      JOIN plantillas pl ON r.plantilla_id = pl.id
      JOIN participantes pa ON r.participante_id = pa.id
      WHERE r.usuario_id = ? ${dateFilter}
      ORDER BY r.created_at DESC
    `).all(...params);

    if (formato === 'csv') {
      const headers = 'ID,Participante,Documento,Codigo,Formulario,Estado,Fecha,GPS Lat,GPS Lng,Huella,Firma\n';
      const rows = registros.map(r =>
        `${r.id},${r.participante},${r.numero_documento},${r.codigo},${r.formulario},${r.estado},${r.created_at},${r.latitud||''},${r.longitud||''},${r.tiene_huella?'Si':'No'},${r.tiene_firma?'Si':'No'}`
      ).join('\n');
      res.setHeader('Content-Type', 'text/csv');
      res.setHeader('Content-Disposition', 'attachment; filename=infomatt360_export.csv');
      return res.send(headers + rows);
    }

    res.json({ total: registros.length, registros });
  } catch (err) {
    res.status(500).json({ error: 'Error al exportar' });
  }
};
