"""Proyecciones independientes de respuestas y observaciones.

No altera tablas ni rutas existentes. Preparado para ser reutilizado por los
exportadores CSV/XLSX sin mezclar datos de revisión con datos de captura.
"""

from __future__ import annotations

import json
from typing import Any, Iterable


def _parse_value(value_json: str) -> Any:
    try:
        return json.loads(value_json)
    except (TypeError, ValueError):
        return value_json


def clean_answer_rows(records: Iterable[Any], values_by_record: dict[str, Iterable[Any]]) -> list[dict[str, Any]]:
    """Una fila por registro, con campos técnicos y respuestas únicamente.

    Los nombres de pregunta se prefijan con 'answer:' para evitar colisiones
    con identificadores técnicos o entre preguntas y metadatos.
    """
    result: list[dict[str, Any]] = []
    for record in records:
        row: dict[str, Any] = {
            "record_id": record.id,
            "project_id": record.project_id,
            "template_id": record.template_id,
            "participant_id": record.participant_id,
        }
        for value in values_by_record.get(record.id, ()):
            row[f"answer:{value.field_name}"] = _parse_value(value.field_value_json)
        result.append(row)
    return result


def review_observation_rows(actions: Iterable[Any]) -> list[dict[str, Any]]:
    """Proyección de observaciones de revisión existentes (ReviewAction).

    Esta fase usa el campo rechazado y la nota ya disponibles. Observaciones
    múltiples por pregunta y rutas REPEAT requieren el modelo posterior.
    """
    return [
        {
            "review_action_id": action.id,
            "record_id": action.record_id,
            "project_id": action.project_id,
            "field_name": action.rejected_field_name,
            "observation": action.notes,
            "reviewer_id": action.user_id,
            "action": action.action,
            "from_status": action.from_status,
            "to_status": action.to_status,
            "created_at": action.created_at,
        }
        for action in actions
        if action.notes or action.rejected_field_name
    ]
