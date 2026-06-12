from pydantic import BaseModel


class BuilderPageCreate(BaseModel):
    template_id: str
    title: str
    description: str | None = None
    sort_order: int = 0
    visible: bool = True


class BuilderPageRead(BuilderPageCreate):
    id: str


class BuilderSectionCreate(BaseModel):
    page_id: str
    title: str
    description: str | None = None
    collapsible: bool = False
    sort_order: int = 0
    visible: bool = True


class BuilderSectionRead(BuilderSectionCreate):
    id: str


class BuilderRowCreate(BaseModel):
    section_id: str
    sort_order: int = 0
    responsive: bool = True


class BuilderRowRead(BuilderRowCreate):
    id: str


class BuilderColumnCreate(BaseModel):
    row_id: str
    desktop_width: int = 12
    tablet_width: int = 12
    mobile_width: int = 12
    sort_order: int = 0


class BuilderColumnRead(BuilderColumnCreate):
    id: str
