"""Sugerencias editables para el constructor a partir de texto de un PDF."""

import re
from io import BytesIO

from pypdf import PdfReader


def _field_type(label: str) -> str:
    text = label.casefold()
    if re.search(r"\b(correo|email|e-mail)\b", text):
        return "EMAIL"
    if re.search(r"\b(teléfono|telefono|celular|móvil|movil)\b", text):
        return "PHONE"
    if re.search(r"\b(fecha|date)\b", text):
        return "DATE"
    if re.search(r"\b(edad|cantidad|número de|numero de|total)\b", text):
        return "NUMBER"
    return "TEXT"


def suggest_pdf_questions(content: bytes) -> dict:
    reader = PdfReader(BytesIO(content))
    if reader.is_encrypted:
        raise ValueError("El PDF está protegido con contraseña")
    if len(reader.pages) > 20:
        raise ValueError("El PDF supera el límite de 20 páginas")
    lines: list[str] = []
    for page in reader.pages:
        lines.extend((page.extract_text() or "").splitlines())
    clean = [re.sub(r"^\s*(?:\d+[.)]|[-•])\s*", "", line).strip() for line in lines]
    title = next((line for line in clean if 5 <= len(line) <= 100), "Formulario importado")
    questions = []
    seen: set[str] = set()
    for line in clean:
        label = line.rstrip(": ").strip()
        if len(label) < 5 or len(label) > 180 or label.casefold() in seen:
            continue
        if not (line.endswith("?") or line.endswith(":") or re.match(r"^(nombre|apellido|documento|correo|email|teléfono|telefono|celular|fecha|edad|municipio|departamento)\b", line, re.I)):
            continue
        seen.add(label.casefold())
        questions.append({"label": label, "type": _field_type(label)})
        if len(questions) == 100:
            break
    if not questions:
        raise ValueError("No se detectaron preguntas. Si el PDF es una imagen escaneada, aplica OCR antes de importarlo")
    return {"title": title, "questions": questions, "page_count": len(reader.pages)}
