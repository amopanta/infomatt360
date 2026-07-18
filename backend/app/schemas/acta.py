from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ActaTemplateCreate(BaseModel):
    """Camino legado: plantilla Jinja2 cruda, sin UI propia (ver docs/109)."""

    project_id: str
    name: str = Field(..., min_length=3)
    html_template: str = Field(..., min_length=1)


class ActaTemplateRead(BaseModel):
    """Representa cualquier fila de `ActaTemplate`, legado o constructor
    visual -- `html_template`/`layout_json`/`template_id` son opcionales
    aqui porque cada camino solo puebla uno de los dos grupos de campos."""

    id: str
    project_id: str
    name: str
    html_template: str | None = None
    layout_json: str | None = None
    template_id: str | None = None
    created_at: datetime
    updated_at: datetime


class ActaRenderRequest(BaseModel):
    data: dict[str, str] = Field(default_factory=dict)


# --- Constructor visual (docs/96 item #4, docs/109) ---


class ActaLogoBlock(BaseModel):
    """Logo/marca de la organizacion -- se inyecta automaticamente desde
    `OrganizationBranding` al momento de renderizar, sin subida manual."""

    type: Literal["logo"] = "logo"
    alignment: Literal["left", "center", "right"] = "left"


class ActaHeaderBlock(BaseModel):
    type: Literal["header"] = "header"
    text: str = Field(..., min_length=1)  # puede contener tokens {{campo}}
    level: Literal[1, 2, 3] = 1


class ActaTableBlock(BaseModel):
    type: Literal["table"] = "table"
    field_names: list[str] = Field(default_factory=list)


class ActaSignatureBlock(BaseModel):
    type: Literal["signature"] = "signature"
    label: str = Field(..., min_length=1)


ActaBlock = Annotated[
    ActaLogoBlock | ActaHeaderBlock | ActaTableBlock | ActaSignatureBlock,
    Field(discriminator="type"),
]


class ActaLayout(BaseModel):
    blocks: list[ActaBlock] = Field(default_factory=list)


class ActaLayoutTemplateCreate(BaseModel):
    project_id: str
    name: str = Field(..., min_length=3)
    template_id: str
    layout: ActaLayout


class ActaRenderFromRecordRequest(BaseModel):
    record_id: str
