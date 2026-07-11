from pydantic import BaseModel, Field


class TenantCleanRequest(BaseModel):
    confirm_slug: str = Field(..., description="Slug exacto de la organizacion, para confirmar la accion critica")
    totp_code: str = Field(..., min_length=6, max_length=6, description="Codigo TOTP vigente del usuario que ejecuta la purga")


class TenantCleanResult(BaseModel):
    organization_id: str
    projects_purged: list[str]
    deleted_counts: dict[str, int]
