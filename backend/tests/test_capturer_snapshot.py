"""docs/145: cada registro guarda quién lo capturó, como estaba su perfil al capturar."""

import csv
import io
import json

from starlette.testclient import TestClient

from app.main import app
from app.models.builder import BuilderTemplate
from app.models.identity import User
from test_form_assignments_reopening import auth, setup_client

PROJECT = "assign-project"


def test_record_keeps_capturer_profile_and_exports_it():
    engine, sessions = setup_client()
    with sessions() as db:
        db.add(BuilderTemplate(id="visita", project_id=PROJECT, name="Visita", status="published"))
        owner = db.query(User).filter(User.email == "assign-owner@example.com").one()
        owner.position, owner.department, owner.municipality = "Gestor de campo", "Antioquia", "Turbo"
        owner_document = owner.document_id
        db.commit()
    with TestClient(app) as client:
        juan = auth(client, "assign-owner@example.com", "Owner12345!")
        admin = auth(client, "assign-admin@example.com", "Admin12345!")
        saved = client.post("/api/v1/runtime/save", headers=juan, json={
            "project_id": PROJECT, "template_id": "visita",
            "values": [{"field_name": "nota", "field_value_json": json.dumps("ok")}]})
        assert saved.status_code == 200, saved.text
        captured = saved.json()["captured_by"]
        assert captured["position"] == "Gestor de campo" and captured["municipality"] == "Turbo"
        assert captured["document_id"] == owner_document

        # Un cambio posterior del perfil no reescribe el registro ya capturado.
        with sessions() as db:
            db.query(User).filter(User.email == "assign-owner@example.com").one().position = "Coordinador"
            db.commit()
        record = client.get(f"/api/v1/runtime/record/{saved.json()['id']}", headers=admin).json()
        assert record["captured_by"]["position"] == "Gestor de campo"

        exported = client.get("/api/v1/runtime/template/visita/records/export.csv", headers=admin)
        rows = list(csv.DictReader(io.StringIO(exported.text.lstrip("﻿"))))
        assert rows[0]["capturador_documento"] == owner_document
        assert rows[0]["capturador_cargo"] == "Gestor de campo" and rows[0]["capturador_municipio"] == "Turbo"
