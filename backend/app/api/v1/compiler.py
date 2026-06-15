"""
Proyecto: InfoMatt360
Modulo: Compiler API
Responsabilidad: Exponer compilacion de formularios para generar Runtime Package.
"""

from typing import Any
from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_current_user
from app.models.identity import User
from app.schemas.runtime_package import RuntimePackage
from app.services.form_compiler import CompilerError, form_compiler

router = APIRouter()


@router.post("/compile", response_model=RuntimePackage)
def compile_template(template: dict[str, Any], current_user: User = Depends(get_current_user)) -> RuntimePackage:
    """Compila un Template JSON a Runtime Package v1.

    Este endpoint es la base de publicacion: si el compiler detecta ciclos o
    errores estructurales, la publicacion debe detenerse.
    """
    try:
        return form_compiler.compile(template)
    except CompilerError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
