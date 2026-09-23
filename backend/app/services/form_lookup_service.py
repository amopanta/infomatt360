"""CSV attachments for XLSForm pulldata(), scoped to a single form."""

import csv
import hashlib
import json
import re
from io import StringIO

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.form_lookup import FormLookup
from app.models.builder import BuilderComponent

MAX_CSV_BYTES = 5 * 1024 * 1024
MAX_ROWS = 50000
NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,120}$")
PULL_RE = re.compile(r"pulldata\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,", re.IGNORECASE)


def referenced_lookup(db: Session, template_id: str, filename: str, column: str, key_column: str) -> bool:
    name = filename[:-4] if filename.lower().endswith(".csv") else filename
    components = db.query(BuilderComponent.config_json).filter(BuilderComponent.template_id == template_id).all()
    for (raw,) in components:
        if not raw:
            continue
        try:
            values = json.loads(raw)
        except ValueError:
            continue
        for expression in (values.get("calculation"), values.get("default"), values.get("relevant_expression"), values.get("constraint_expression")):
            if isinstance(expression, str) and any(
                (file[:-4] if file.lower().endswith(".csv") else file, result, index) == (name, column, key_column)
                for file, result, index in PULL_RE.findall(expression)
            ):
                return True
    return False


def normalize_name(filename: str) -> str:
    name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if not name.lower().endswith(".csv"):
        raise HTTPException(status_code=422, detail="Adjunta un archivo CSV")
    name = name[:-4]
    if not NAME_RE.fullmatch(name):
        raise HTTPException(status_code=422, detail="El nombre del CSV sólo puede contener letras, números, guion y guion bajo")
    return name


def parse_csv(content: bytes) -> tuple[list[str], list[dict[str, str]]]:
    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(status_code=413, detail="El CSV supera 5 MB")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Guarda el CSV en UTF-8") from exc
    reader = csv.DictReader(StringIO(text, newline=""))
    columns = [value.strip() for value in (reader.fieldnames or [])]
    if len(columns) < 2 or any(not value for value in columns) or len(set(columns)) != len(columns):
        raise HTTPException(status_code=422, detail="El CSV necesita al menos dos columnas con encabezados únicos")
    rows: list[dict[str, str]] = []
    for index, row in enumerate(reader, 2):
        if index > MAX_ROWS + 1:
            raise HTTPException(status_code=413, detail="El CSV supera 50.000 filas")
        if None in row:
            raise HTTPException(status_code=422, detail=f"Fila {index}: más valores que columnas")
        rows.append({key.strip(): (value or "").strip() for key, value in row.items()})
    return columns, rows


def put_lookup(db: Session, project_id: str, template_id: str, filename: str, content: bytes) -> FormLookup:
    name = normalize_name(filename)
    columns, rows = parse_csv(content)
    item = db.query(FormLookup).filter(FormLookup.template_id == template_id, FormLookup.name == name).first()
    if item is None:
        item = FormLookup(project_id=project_id, template_id=template_id, name=name)
        db.add(item)
    item.columns_json = json.dumps(columns, ensure_ascii=False)
    item.rows_json = json.dumps(rows, ensure_ascii=False)
    item.row_count = len(rows)
    item.checksum = hashlib.sha256(content).hexdigest()
    item.updated_at = utc_now()
    db.commit()
    db.refresh(item)
    return item


def lookup_value(db: Session, template_id: str, filename: str, column: str, key_column: str, key_value: str) -> str:
    name = filename[:-4] if filename.lower().endswith(".csv") else filename
    item = db.query(FormLookup).filter(FormLookup.template_id == template_id, FormLookup.name == name).first()
    if item is None:
        raise HTTPException(status_code=404, detail=f"Falta el CSV {name}.csv")
    columns = json.loads(item.columns_json)
    if column not in columns or key_column not in columns:
        raise HTTPException(status_code=422, detail="La columna solicitada no existe en el CSV")
    needle = str(key_value).strip()
    for row in json.loads(item.rows_json):
        if row.get(key_column, "").strip() == needle:
            return row.get(column, "")
    return ""
