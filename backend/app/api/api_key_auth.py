from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.api_key import ApiKeyAuthContext
from app.services.api_key_service import api_key_service, to_read


def get_api_key_context(x_api_key: str | None = Header(default=None, alias="X-API-Key"), db: Session = Depends(get_db)) -> ApiKeyAuthContext:
    if not x_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key requerida")
    row = api_key_service.authenticate(db, x_api_key)
    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key invalida o revocada")
    data = to_read(row)
    return ApiKeyAuthContext(project_id=data.project_id, key_id=data.key_id, permissions=data.permissions)


def require_api_key_permission(permission: str):
    def dependency(context: ApiKeyAuthContext = Depends(get_api_key_context)) -> ApiKeyAuthContext:
        if permission not in context.permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permiso insuficiente para API key")
        return context

    return dependency
