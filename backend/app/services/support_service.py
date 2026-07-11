"""Mesa de ayuda y ticketing automatizado no-code.

Motor de reglas semanticas basado en palabras clave (arbol de decision
simple, sin dependencia de un LLM): si la descripcion del problema
contiene senales de daño fisico del dispositivo, el ticket siempre se
escala a soporte humano sin importar otras coincidencias. Si no, se
compara contra un catalogo de patrones conocidos y, de coincidir, se
responde de forma autonoma con un tutorial; de lo contrario se escala a
un humano por no reconocer el patron.
"""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.models.support import SupportTicket
from app.schemas.support import SupportTicketCreate, SupportTicketRead

PHYSICAL_DAMAGE_KEYWORDS = [
    "pantalla rota",
    "pantalla partida",
    "pantalla quebrada",
    "no enciende",
    "se cayo",
    "se me cayo",
    "dañado",
    "danado",
    "golpeado",
    "mojado",
    "se mojo",
]

AUTO_RESPONSE_RULES: list[tuple[str, list[str], str]] = [
    (
        "sync_help",
        ["sincronizacion", "no sincroniza", "sincroniza", "sync"],
        "Verifica tu conexion a internet o datos moviles, abre la app y desliza para forzar "
        "una sincronizacion manual. Si el problema persiste, cierra sesion y vuelve a "
        "iniciarla para restablecer la cola de sincronizacion local.",
    ),
    (
        "gps_help",
        ["no lee el gps", "no detecta ubicacion", "gps", "ubicacion"],
        "Activa los permisos de ubicacion de la aplicacion desde los ajustes del dispositivo "
        "y sal a un espacio abierto sin techo; el GPS puede tardar hasta 30 segundos en "
        "obtener señal en zonas rurales.",
    ),
    (
        "camera_help",
        ["no abre la camara", "camara", "foto no carga", "no carga la foto"],
        "Revisa que la app tenga permiso de camara y almacenamiento en los ajustes del "
        "dispositivo, y libera espacio si el almacenamiento esta lleno.",
    ),
    (
        "login_help",
        ["no puedo iniciar sesion", "clave incorrecta", "olvide mi contraseña", "olvide mi clave", "bloqueado"],
        "Usa la opcion \"Olvide mi contraseña\" en la pantalla de inicio de sesion, o solicita "
        "a tu coordinador una credencial de emergencia si no tienes acceso a tu correo.",
    ),
]


def _to_read(row: SupportTicket) -> SupportTicketRead:
    return SupportTicketRead(
        id=row.id,
        project_id=row.project_id,
        created_by=row.created_by,
        subject=row.subject,
        description=row.description,
        status=row.status,
        resolution_channel=row.resolution_channel,
        matched_rule=row.matched_rule,
        auto_response_text=row.auto_response_text,
        resolved_by=row.resolved_by,
        resolved_at=row.resolved_at,
        created_at=row.created_at,
    )


class SupportService:
    def _classify(self, subject: str, description: str) -> tuple[str, str, str | None, str | None]:
        normalized = f"{subject} {description}".lower()

        if any(keyword in normalized for keyword in PHYSICAL_DAMAGE_KEYWORDS):
            return "open", "human", "physical_damage", None

        for rule_key, keywords, tutorial in AUTO_RESPONSE_RULES:
            if any(keyword in normalized for keyword in keywords):
                return "auto_resolved", "auto", rule_key, tutorial

        return "open", "human", None, None

    def create_ticket(self, db: Session, payload: SupportTicketCreate, created_by: str) -> SupportTicketRead:
        status_value, resolution_channel, matched_rule, auto_response_text = self._classify(payload.subject, payload.description)
        row = SupportTicket(
            project_id=payload.project_id,
            created_by=created_by,
            subject=payload.subject,
            description=payload.description,
            status=status_value,
            resolution_channel=resolution_channel,
            matched_rule=matched_rule,
            auto_response_text=auto_response_text,
            resolved_at=utc_now() if status_value == "auto_resolved" else None,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _to_read(row)

    def list_tickets(self, db: Session, project_id: str, status_filter: str | None = None) -> list[SupportTicketRead]:
        query = db.query(SupportTicket).filter(SupportTicket.project_id == project_id)
        if status_filter:
            query = query.filter(SupportTicket.status == status_filter)
        rows = query.order_by(SupportTicket.created_at.desc()).all()
        return [_to_read(row) for row in rows]

    def resolve_ticket(self, db: Session, ticket_id: str, resolved_by: str) -> SupportTicketRead:
        row = db.query(SupportTicket).filter(SupportTicket.id == ticket_id).first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket no encontrado")
        row.status = "resolved"
        row.resolved_by = resolved_by
        row.resolved_at = utc_now()
        db.commit()
        db.refresh(row)
        return _to_read(row)


support_service = SupportService()
