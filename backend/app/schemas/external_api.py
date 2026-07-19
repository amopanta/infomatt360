from datetime import datetime

from pydantic import BaseModel, Field


class ExternalRecordTabularRow(BaseModel):
    """Fila plana de un registro Runtime para consumo por BI (Power BI, Tableau).

    `fields` va anidado (no aplanado al nivel superior) a proposito: el
    nombre de un campo de formulario (BuilderComponent.name) es texto libre
    definido por quien construye el formulario -- nada impide que alguien lo
    llame "status" o "record_id", lo que colisionaria con las columnas fijas
    del sobre si se aplanara todo a un mismo nivel."""

    record_id: str
    status: str
    submitted_by: str | None = None
    participant_id: str | None = None
    created_at: datetime
    updated_at: datetime
    fields: dict[str, object] = Field(default_factory=dict)


class ExternalRecordTabularPage(BaseModel):
    """`columns` es estable entre llamadas: se deriva del esquema del
    formulario (BuilderComponent.name, orden = sort_order), no de que
    campos aparecieron en este lote de resultados -- ver
    runtime_record_service.search_template_records_tabular."""

    template_id: str
    columns: list[str] = Field(default_factory=list)
    items: list[ExternalRecordTabularRow] = Field(default_factory=list)
    total: int
    limit: int
    offset: int
