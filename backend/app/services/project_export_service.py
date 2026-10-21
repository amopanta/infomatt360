"""Exportación de un proyecto completo a una base externa (docs/146).

Con una sola conexión (un destino de la base espejo) se copian, sin configurar
formulario por formulario:

- `im360_forms` y `im360_form_fields`: catálogo y diccionario de datos;
- `im360_participants` y `im360_assignments`;
- `im360_records` (con quien capturó) y `im360_record_values` (clave-valor);
- una tabla plana por formulario, `im360_f_<nombre>_<id>`, con una columna
  por pregunta. Si el formulario gana preguntas, la tabla gana columnas.

Todas las tablas fijas llevan `project_id`, así varios proyectos pueden
compartir la misma base destino. Al final se cuentan las filas de origen y
destino de cada tabla (conciliación).
"""

from __future__ import annotations

import json
import re
import unicodedata
from datetime import datetime
from typing import Iterable

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, UnicodeText, func, inspect, select, text
from sqlalchemy.dialects import mssql, mysql
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session

from app.models.builder import BuilderComponent, BuilderTemplate
from app.models.form_assignment import ParticipantFormAssignment
from app.models.participants import Participant
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue

CHUNK = 500
# Texto largo en cada motor: NVARCHAR(max) en SQL Server (no el obsoleto NTEXT) y LONGTEXT en MySQL.
LONG_TEXT = UnicodeText().with_variant(mssql.NVARCHAR(), "mssql").with_variant(mysql.LONGTEXT(), "mysql", "mariadb")
NON_DATA_TYPES = {"NOTE", "LABEL", "SECTION"}
META_COLUMNS = [
    "im_record_id", "im_status", "im_participant_id", "im_participant_document", "im_participant_code", "im_participant_name",
    "im_department", "im_municipality", "im_captured_by", "im_captured_by_document", "im_captured_by_position",
    "im_captured_by_municipality", "im_created_at", "im_updated_at",
]


def fixed_tables() -> tuple[MetaData, dict[str, Table]]:
    metadata = MetaData()
    tables = {
        "forms": Table("im360_forms", metadata,
                       Column("id", String(36), primary_key=True), Column("project_id", String(36), nullable=False, index=True),
                       Column("name", String(180), nullable=False), Column("status", String(40), nullable=False),
                       Column("flat_table", String(80), nullable=False), Column("exported_at", DateTime, nullable=False)),
        "fields": Table("im360_form_fields", metadata,
                        Column("id", String(80), primary_key=True), Column("project_id", String(36), nullable=False, index=True),
                        Column("template_id", String(36), nullable=False), Column("field_name", String(180), nullable=False),
                        Column("column_name", String(80), nullable=False), Column("label", LONG_TEXT, nullable=True),
                        Column("field_type", String(80), nullable=True), Column("position", Integer, nullable=False)),
        "participants": Table("im360_participants", metadata,
                              Column("id", String(36), primary_key=True), Column("project_id", String(36), nullable=False, index=True),
                              Column("document_id", String(80), nullable=True), Column("external_code", String(120), nullable=True),
                              Column("full_name", String(220), nullable=False), Column("participant_type", String(80), nullable=True),
                              Column("status", String(40), nullable=True), Column("department", String(120), nullable=True),
                              Column("municipality", String(120), nullable=True), Column("group_name", String(180), nullable=True),
                              Column("metadata_json", LONG_TEXT, nullable=True), Column("created_at", DateTime, nullable=True)),
        "assignments": Table("im360_assignments", metadata,
                             Column("id", String(36), primary_key=True), Column("project_id", String(36), nullable=False, index=True),
                             Column("template_id", String(36), nullable=False), Column("participant_id", String(36), nullable=False),
                             Column("responsible_user_id", String(36), nullable=False), Column("status", String(30), nullable=False),
                             Column("created_at", DateTime, nullable=True), Column("updated_at", DateTime, nullable=True)),
        "records": Table("im360_records", metadata,
                         Column("id", String(36), primary_key=True), Column("project_id", String(36), nullable=False, index=True),
                         Column("template_id", String(36), nullable=False), Column("status", String(40), nullable=False),
                         Column("participant_id", String(36), nullable=True), Column("parent_record_id", String(36), nullable=True),
                         Column("submitted_by", String(36), nullable=True), Column("captured_by_name", String(180), nullable=True),
                         Column("captured_by_document", String(50), nullable=True), Column("captured_by_position", String(120), nullable=True),
                         Column("captured_by_municipality", String(120), nullable=True),
                         Column("created_at", DateTime, nullable=False), Column("updated_at", DateTime, nullable=False)),
        "values": Table("im360_record_values", metadata,
                        Column("id", String(36), primary_key=True), Column("project_id", String(36), nullable=False, index=True),
                        Column("record_id", String(36), nullable=False, index=True), Column("field_name", String(180), nullable=False),
                        Column("field_value_json", LONG_TEXT, nullable=False)),
    }
    return metadata, tables


def slug(value: str, limit: int) -> str:
    plain = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii").lower()
    plain = re.sub(r"[^a-z0-9]+", "_", plain).strip("_")
    return (plain or "campo")[:limit].rstrip("_") or "campo"


def flat_table_name(template: BuilderTemplate) -> str:
    return f"im360_f_{slug(template.name, 30)}_{template.id.replace('-', '')[:8]}"


def column_names(field_names: Iterable[str]) -> dict[str, str]:
    """Nombre de columna seguro y único por campo (minúsculas, sin tildes, máx. 60)."""
    used = set(META_COLUMNS)
    result: dict[str, str] = {}
    for name in field_names:
        base = slug(name, 56)
        candidate, index = base, 2
        while candidate in used:
            candidate = f"{base[:52]}_{index}"
            index += 1
        used.add(candidate)
        result[name] = candidate
    return result


def flat_value(raw: str) -> str | None:
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return raw
    if value is None or value == "":
        return None
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _metadata(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
        return value if isinstance(value, dict) else {}
    except ValueError:
        return {}


def _chunks(rows: list[dict]) -> Iterable[list[dict]]:
    for start in range(0, len(rows), CHUNK):
        yield rows[start:start + CHUNK]


def _insert(conn: Connection, table: Table, rows: list[dict]) -> None:
    for chunk in _chunks(rows):
        conn.execute(table.insert(), chunk)


def _ensure_flat_table(engine: Engine, conn: Connection, name: str, columns: list[str]) -> Table:
    """Crea la tabla plana o le agrega las columnas nuevas (nunca borra columnas)."""
    metadata = MetaData()
    existing = {column["name"] for column in inspect(conn).get_columns(name)} if inspect(conn).has_table(name) else None
    wanted = META_COLUMNS + columns
    if existing is None:
        table = Table(name, metadata, Column("im_record_id", String(36), primary_key=True),
                      *[Column(col, DateTime if col in {"im_created_at", "im_updated_at"} else LONG_TEXT if col not in META_COLUMNS else String(220), nullable=True)
                        for col in wanted if col != "im_record_id"])
        metadata.create_all(conn, tables=[table])
        return table
    quote = engine.dialect.identifier_preparer.quote
    text_type = LONG_TEXT.compile(dialect=engine.dialect)
    keyword = "ADD" if engine.dialect.name == "mssql" else "ADD COLUMN"
    for col in wanted:
        if col not in existing:
            conn.execute(text(f"ALTER TABLE {quote(name)} {keyword} {quote(col)} {text_type}"))
    return Table(name, MetaData(), autoload_with=conn)


def _count(conn: Connection, table: Table, project_id: str | None) -> int:
    query = select(func.count()).select_from(table)
    if project_id is not None:
        query = query.where(table.c.project_id == project_id)
    return int(conn.execute(query).scalar() or 0)


def export_project(db: Session, engine: Engine, project_id: str, mode: str, watermark: datetime | None) -> dict:
    """Copia el proyecto. `mode`: full_mirror (reemplaza lo del proyecto),
    incremental (solo registros nuevos o cambiados desde `watermark`) o
    insert_only (solo registros que aún no están en el destino)."""
    metadata, tables = fixed_tables()
    metadata.create_all(engine, checkfirst=True)
    templates = db.query(BuilderTemplate).filter(BuilderTemplate.project_id == project_id).order_by(BuilderTemplate.name).all()
    template_ids = [t.id for t in templates]
    components = db.query(BuilderComponent).filter(BuilderComponent.template_id.in_(template_ids)).all() if template_ids else []
    participants = db.query(Participant).filter(Participant.project_id == project_id).all()
    assignments = db.query(ParticipantFormAssignment).filter(ParticipantFormAssignment.project_id == project_id).all()
    records = db.query(RuntimeRecord).filter(RuntimeRecord.project_id == project_id).all()
    record_ids = [r.id for r in records]
    values: list[RuntimeRecordValue] = []
    for start in range(0, len(record_ids), CHUNK):
        values.extend(db.query(RuntimeRecordValue).filter(RuntimeRecordValue.record_id.in_(record_ids[start:start + CHUNK])).all())
    values_by_record: dict[str, list[RuntimeRecordValue]] = {}
    for value in values:
        values_by_record.setdefault(value.record_id, []).append(value)
    participants_by_id = {p.id: p for p in participants}
    now = datetime.utcnow()

    # Columnas por formulario: preguntas en su orden y, al final, campos que
    # solo aparecen en respuestas (formularios antiguos o importados).
    fields_by_template: dict[str, list[tuple[str, str | None, str | None]]] = {t.id: [] for t in templates}
    for component in sorted(components, key=lambda c: (getattr(c, "sort_order", 0) or 0, c.name)):
        if component.component_type.upper() in NON_DATA_TYPES:
            continue
        if component.name not in {name for name, _, _ in fields_by_template[component.template_id]}:
            fields_by_template[component.template_id].append((component.name, component.label, component.component_type))
    for record in records:
        known = {name for name, _, _ in fields_by_template.get(record.template_id, [])}
        for value in values_by_record.get(record.id, []):
            if record.template_id in fields_by_template and value.field_name not in known:
                fields_by_template[record.template_id].append((value.field_name, None, None))
                known.add(value.field_name)

    if mode == "incremental" and watermark is not None:
        changed = [r for r in records if r.updated_at >= watermark or r.created_at >= watermark]
    else:
        changed = list(records)
    flat_summary: dict[str, dict] = {}

    with engine.begin() as conn:
        # Catálogo, diccionario, participantes y asignaciones: siempre completos (son pequeños y cambian sin marca de tiempo).
        for key in ("forms", "fields", "participants", "assignments"):
            conn.execute(tables[key].delete().where(tables[key].c.project_id == project_id))
        _insert(conn, tables["forms"], [{"id": t.id, "project_id": project_id, "name": t.name, "status": t.status,
                                          "flat_table": flat_table_name(t), "exported_at": now} for t in templates])
        field_rows = []
        for template in templates:
            mapping = column_names(name for name, _, _ in fields_by_template[template.id])
            for position, (name, label, field_type) in enumerate(fields_by_template[template.id], start=1):
                field_rows.append({"id": f"{template.id[:36]}:{position}"[:80], "project_id": project_id, "template_id": template.id,
                                   "field_name": name, "column_name": mapping[name], "label": label, "field_type": field_type,
                                   "position": position})
        _insert(conn, tables["fields"], field_rows)
        participant_rows = []
        for p in participants:
            meta = _metadata(p.metadata_json)
            participant_rows.append({"id": p.id, "project_id": project_id, "document_id": p.document_id, "external_code": p.external_code,
                                     "full_name": p.full_name, "participant_type": p.participant_type, "status": p.status,
                                     "department": str(meta.get("department") or meta.get("departamento") or "") or None,
                                     "municipality": str(meta.get("municipality") or meta.get("municipio") or "") or None,
                                     "group_name": str(meta.get("group_name") or "") or None, "metadata_json": p.metadata_json,
                                     "created_at": p.created_at})
        _insert(conn, tables["participants"], participant_rows)
        _insert(conn, tables["assignments"], [{"id": a.id, "project_id": project_id, "template_id": a.template_id, "participant_id": a.participant_id,
                                                "responsible_user_id": a.responsible_user_id, "status": a.status,
                                                "created_at": a.created_at, "updated_at": a.updated_at} for a in assignments])

        # Registros y valores.
        if mode == "full_mirror":
            conn.execute(tables["values"].delete().where(tables["values"].c.project_id == project_id))
            conn.execute(tables["records"].delete().where(tables["records"].c.project_id == project_id))
            to_write = list(records)
        else:
            changed_ids = [r.id for r in changed]
            existing: set[str] = set()
            for start in range(0, len(changed_ids), CHUNK):
                existing |= {row[0] for row in conn.execute(select(tables["records"].c.id).where(tables["records"].c.id.in_(changed_ids[start:start + CHUNK])))}
            if mode == "insert_only":
                to_write = [r for r in changed if r.id not in existing]
            else:
                to_write = changed
                stale = list(existing)
                for start in range(0, len(stale), CHUNK):
                    part = stale[start:start + CHUNK]
                    conn.execute(tables["values"].delete().where(tables["values"].c.record_id.in_(part)))
                    conn.execute(tables["records"].delete().where(tables["records"].c.id.in_(part)))
        _insert(conn, tables["records"], [{
            "id": r.id, "project_id": project_id, "template_id": r.template_id, "status": r.status, "participant_id": r.participant_id,
            "parent_record_id": r.parent_record_id, "submitted_by": r.submitted_by, "captured_by_name": r.captured_by_name,
            "captured_by_document": r.captured_by_document, "captured_by_position": r.captured_by_position,
            "captured_by_municipality": r.captured_by_municipality, "created_at": r.created_at, "updated_at": r.updated_at,
        } for r in to_write])
        _insert(conn, tables["values"], [{"id": v.id, "project_id": project_id, "record_id": v.record_id, "field_name": v.field_name,
                                           "field_value_json": v.field_value_json}
                                          for r in to_write for v in values_by_record.get(r.id, [])])

        # Una tabla plana por formulario (registros principales; los hijos de un REPEAT van en clave-valor).
        written_ids = {r.id for r in to_write}
        for template in templates:
            mapping = column_names(name for name, _, _ in fields_by_template[template.id])
            name = flat_table_name(template)
            table = _ensure_flat_table(engine, conn, name, list(mapping.values()))
            own = [r for r in records if r.template_id == template.id and r.parent_record_id is None]
            rows = []
            for record in own:
                if record.id not in written_ids:
                    continue
                participant = participants_by_id.get(record.participant_id or "")
                meta = _metadata(participant.metadata_json) if participant else {}
                row = {col: None for col in table.c.keys()}
                row.update({
                    "im_record_id": record.id, "im_status": record.status, "im_participant_id": record.participant_id,
                    "im_participant_document": participant.document_id if participant else None,
                    "im_participant_code": participant.external_code if participant else None,
                    "im_participant_name": participant.full_name if participant else None,
                    "im_department": str(meta.get("department") or meta.get("departamento") or "") or None,
                    "im_municipality": str(meta.get("municipality") or meta.get("municipio") or "") or record.captured_by_municipality,
                    "im_captured_by": record.captured_by_name, "im_captured_by_document": record.captured_by_document,
                    "im_captured_by_position": record.captured_by_position, "im_captured_by_municipality": record.captured_by_municipality,
                    "im_created_at": record.created_at, "im_updated_at": record.updated_at,
                })
                for value in values_by_record.get(record.id, []):
                    column = mapping.get(value.field_name)
                    if column:
                        row[column] = flat_value(value.field_value_json)
                rows.append(row)
            if mode == "full_mirror":
                conn.execute(table.delete())
            elif rows:
                ids = [row["im_record_id"] for row in rows]
                for start in range(0, len(ids), CHUNK):
                    conn.execute(table.delete().where(table.c.im_record_id.in_(ids[start:start + CHUNK])))
            if mode == "insert_only":
                present = set()
                ids = [row["im_record_id"] for row in rows]
                for start in range(0, len(ids), CHUNK):
                    present |= {r[0] for r in conn.execute(select(table.c.im_record_id).where(table.c.im_record_id.in_(ids[start:start + CHUNK])))}
                rows = [row for row in rows if row["im_record_id"] not in present]
            _insert(conn, table, rows)
            flat_summary[name] = {"form": template.name, "source": len(own), "destination": _count(conn, table, None), "columns": len(mapping)}

        source_counts = {"forms": len(templates), "fields": len(field_rows), "participants": len(participants), "assignments": len(assignments),
                         "records": len(records), "values": len(values)}
        tables_summary = {}
        for key, table in tables.items():
            destination = _count(conn, table, project_id)
            tables_summary[table.name] = {"source": source_counts[key], "destination": destination, "ok": source_counts[key] == destination}
    for item in flat_summary.values():
        item["ok"] = item["source"] == item["destination"]
    return {
        "scope": "project", "mode": mode, "written_records": len(to_write),
        "written_values": sum(len(values_by_record.get(r.id, [])) for r in to_write),
        "tables": tables_summary, "form_tables": flat_summary,
        "reconciled": all(t["ok"] for t in tables_summary.values()) and all(t["ok"] for t in flat_summary.values()),
    }
