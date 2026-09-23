from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
import pytest

from app.db.base import Base
from app.models.builder import BuilderComponent
from app.services.form_lookup_service import lookup_value, put_lookup, referenced_lookup


def test_pulldata_csv_upload_and_replace_preserves_form_reference():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        first = put_lookup(db, "project", "form", "familias.csv", b"codigo,nombre,estado\n001,Ana,activo\n002,Luis,inactivo\n")
        assert first.row_count == 2
        assert lookup_value(db, "form", "familias", "nombre", "codigo", "001") == "Ana"
        assert lookup_value(db, "form", "familias.csv", "nombre", "codigo", "003") == ""
        replacement = put_lookup(db, "project", "form", "familias.csv", "codigo,nombre\n001,María\n".encode())
        assert replacement.id == first.id
        assert lookup_value(db, "form", "familias", "nombre", "codigo", "001") == "María"
        with pytest.raises(HTTPException):
            lookup_value(db, "other-form", "familias", "nombre", "codigo", "001")


def test_pulldata_rejects_malformed_csv_without_mutating_existing_file():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        put_lookup(db, "project", "form", "familias.csv", b"codigo,nombre\n1,Ana\n")
        with pytest.raises(HTTPException):
            put_lookup(db, "project", "form", "familias.csv", b"codigo,codigo\n1,Ana\n")
        assert lookup_value(db, "form", "familias", "nombre", "codigo", "1") == "Ana"


def test_public_lookup_only_exposes_columns_referenced_by_the_form():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with sessionmaker(bind=engine)() as db:
        db.add(BuilderComponent(template_id="form", component_type="HIDDEN", name="nombre", label="Nombre", config_json='{"calculation": "pulldata(\u0027familias\u0027, \u0027nombre\u0027, \u0027codigo\u0027, ${codigo})"}'))
        db.commit()
        assert referenced_lookup(db, "form", "familias", "nombre", "codigo")
        assert not referenced_lookup(db, "form", "familias", "documento", "codigo")
