"""Response availability shared by public links and authenticated capture."""

from app.core.time import utc_now
from app.models.builder import BuilderTemplate


def availability(template: BuilderTemplate) -> str:
    now = utc_now()
    if template.status == "archived":
        return "archived"
    if template.status == "paused":
        return "paused"
    if template.status != "published":
        return "draft"
    if template.starts_at is not None and now < template.starts_at:
        return "scheduled"
    if template.ends_at is not None and now >= template.ends_at:
        return "closed"
    return "accepting"


def ensure_accepting(template: BuilderTemplate) -> None:
    state = availability(template)
    messages = {
        "draft": "El formulario no esta publicado",
        "paused": "La recepcion de respuestas esta detenida",
        "archived": "El formulario esta archivado",
        "scheduled": "La fecha de inicio del formulario aun no ha llegado",
        "closed": "La fecha de finalizacion del formulario ya paso",
    }
    if state != "accepting":
        raise ValueError(messages[state])
