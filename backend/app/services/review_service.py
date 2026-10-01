import json
from urllib.parse import quote

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.time import utc_now
from app.models.assignment import UserProjectAssignment
from typing import Any
from app.models.identity import User
from app.models.messages import InternalMessage
from app.models.records import Record, RecordEvent
from app.models.review import ReviewAction
from app.models.audit import AuditLog
from app.models.runtime_record import RuntimeRecord
from app.schemas.review import ReviewActionCreate, ReviewActionRead
from app.services.approval_flow_service import approval_flow_service
from app.services.erp_service import erp_service
from app.services.form_assignment_service import set_assignment_status
from app.services.integration_service import integration_service
from app.services.whatsapp_service import whatsapp_service


ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"submitted", "cancelled"},
    "submitted": {"under_review", "approved", "rejected", "returned", "archived", "voided"},
    "under_review": {"tech_approved", "approved", "rejected", "returned", "archived", "voided"},
    "tech_approved": {"coordinator_approved", "approved", "rejected", "returned", "archived", "voided"},
    "coordinator_approved": {"approved", "rejected", "returned", "archived", "voided"},
    "returned": {"corrected", "cancelled", "archived", "voided"},
    "corrected": {"submitted", "under_review", "archived", "voided"},
    "approved": {"archived", "synced", "voided"},
    "rejected": {"archived", "voided"},
    "cancelled": set(),
    "archived": {"voided"},
    # "sincronizado": confirma que el registro aprobado llego a un sistema
    # externo (donante/ActivityInfo, ver docs/86). Se puede marcar manualmente
    # o queda asignado automaticamente por review_service.apply_action cuando
    # integration_service.push_approved_record() tiene exito.
    "synced": {"archived", "voided"},
    # "anulado": invalidacion formal de un registro, distinta de "cancelled"
    # (abandonar un borrador antes de enviarlo) y de "rejected" (no paso
    # control de calidad). Nunca borra el registro ni su historial -- solo
    # marca que ya no es valido, preservando la trazabilidad completa.
    "voided": set(),
}


def to_read(row: ReviewAction) -> ReviewActionRead:
    return ReviewActionRead(
        id=row.id,
        project_id=row.project_id,
        record_id=row.record_id,
        from_status=row.from_status,
        to_status=row.to_status,
        action=row.action,
        notes=row.notes,
        rejected_field_name=row.rejected_field_name,
        user_id=row.user_id,
        approval_flow_id=row.approval_flow_id,
        approval_flow_version=row.approval_flow_version,
        created_at=row.created_at,
    )


class ReviewService:
    def apply_action(self, db: Session, payload: ReviewActionCreate, user_id: str, configured_step: Any | None = None) -> ReviewActionRead:
        record = self._find_runtime_or_legacy_record(db, payload.record_id)
        if record is None:
            raise ValueError("Registro no encontrado")
        if record.project_id != payload.project_id:
            raise ValueError("El registro no pertenece al proyecto indicado")
        from_status = record.status if record else None
        if from_status == "approved" and payload.to_status == "returned":
            raise ValueError("Usa la reapertura administrativa con motivo obligatorio")
        if payload.to_status == "returned" and not (payload.notes or "").strip():
            raise ValueError("El motivo de devolución es obligatorio")
        template_id = self._record_template_id(record)
        snapshot_json = self._record_approval_snapshot(record)
        self._validate_transition(db, payload, from_status, template_id, snapshot_json)
        should_advance = self._should_advance_configured_step(db, payload, user_id, from_status, configured_step)

        if should_advance:
            record.status = payload.to_status
            if isinstance(record, RuntimeRecord):
                assignment_status = {"submitted": "completed", "under_review": "completed", "returned": "in_progress", "corrected": "in_progress", "approved": "closed"}.get(payload.to_status)
                if assignment_status:
                    set_assignment_status(db, record.template_id, record.participant_id, assignment_status)
            if isinstance(record, Record):
                record.updated_by = user_id
            if hasattr(record, "updated_at"):
                record.updated_at = utc_now()
            # Liquidacion ERP (inventario + honorarios): si la plantilla no
            # tiene ErpTemplateConfig, es un no-op. Si lanza ValueError (SKU
            # inexistente, stock insuficiente), la excepcion se propaga antes
            # de cualquier commit y descarta tambien este cambio de estado.
            if isinstance(record, RuntimeRecord) and payload.to_status == "approved":
                erp_service.settle_record(db, record)
                # Interoperabilidad con plataformas de donantes (ActivityInfo/
                # TolaData u otras via conector generico): fire-and-forget, no
                # bloquea la aprobacion si el envio externo falla.
                integration_job = integration_service.push_approved_record(db, record)
                # "Sincronizado" (ver docs/100): solo se avanza automaticamente
                # si el envio realmente tuvo exito (job.status == "sent"). Si
                # no hay integracion configurada (job es None) o el envio
                # fallo, el registro se queda en "approved" -- la aprobacion en
                # si nunca se revierte ni se bloquea por esto.
                if integration_job is not None and integration_job.status == "sent":
                    record.status = "synced"
                    db.add(ReviewAction(
                        project_id=payload.project_id,
                        record_id=payload.record_id,
                        from_status="approved",
                        to_status="synced",
                        action="auto_synced",
                        notes="Sincronizado automaticamente tras el envio exitoso a la integracion de donante.",
                        user_id=user_id,
                    ))

        row = ReviewAction(
            project_id=payload.project_id,
            record_id=payload.record_id,
            from_status=from_status,
            to_status=payload.to_status,
            action=payload.action,
            notes=payload.notes,
            rejected_field_name=payload.rejected_field_name,
            user_id=user_id,
            approval_flow_id=configured_step.flow_id if configured_step else None,
            approval_flow_version=self._configured_step_flow_version(db, configured_step),
        )
        db.add(row)
        db.add(RecordEvent(record_id=payload.record_id, event_type=payload.action, user_id=user_id, notes=payload.notes))
        db.add(AuditLog(project_id=payload.project_id, user_id=user_id, module="records", action="review_status",
                        entity_type="runtime_record" if isinstance(record, RuntimeRecord) else "record", entity_id=record.id,
                        before_json=json.dumps({"status": from_status}), after_json=json.dumps({"status": payload.to_status, "notes": payload.notes})))
        if should_advance:
            self._add_status_notification(db, record, payload, from_status, user_id)
        db.commit()
        db.refresh(row)
        return to_read(row)

    def reopen_approved(self, db: Session, record_id: str, user_id: str, reason: str) -> ReviewActionRead:
        record = self._find_runtime_or_legacy_record(db, record_id)
        if not record:
            raise ValueError("Registro no encontrado")
        if record.status != "approved":
            raise ValueError("Solo se puede reabrir un registro aprobado que no esté sincronizado")
        if isinstance(record, RuntimeRecord):
            erp_service.reverse_settlement(db, record)
            set_assignment_status(db, record.template_id, record.participant_id, "in_progress")
        record.status = "returned"
        record.updated_at = utc_now()
        row = ReviewAction(project_id=record.project_id, record_id=record.id, from_status="approved",
                           to_status="returned", action="admin_reopen", notes=reason.strip(), user_id=user_id)
        db.add(row)
        db.add(RecordEvent(record_id=record.id, event_type="admin_reopen", user_id=user_id, notes=reason.strip()))
        db.add(AuditLog(project_id=record.project_id, user_id=user_id, module="records", action="reopen_approved",
                        entity_type="runtime_record" if isinstance(record, RuntimeRecord) else "record", entity_id=record.id,
                        before_json=json.dumps({"status": "approved"}),
                        after_json=json.dumps({"status": "returned", "reason": reason.strip()})))
        db.commit()
        db.refresh(row)
        return to_read(row)

    def list_actions(self, db: Session, record_id: str) -> list[ReviewActionRead]:
        rows = db.query(ReviewAction).filter(ReviewAction.record_id == record_id).order_by(ReviewAction.created_at.desc()).all()
        return [to_read(row) for row in rows]

    def get_record_project_id(self, db: Session, record_id: str) -> str | None:
        record = self._find_runtime_or_legacy_record(db, record_id)
        return record.project_id if record else None

    def get_record_context(self, db: Session, record_id: str) -> tuple[str, str | None, str] | None:
        record = self._find_runtime_or_legacy_record(db, record_id)
        if not record:
            return None
        return record.project_id, self._record_template_id(record), record.status

    def get_record_review_context(self, db: Session, record_id: str) -> tuple[str, str | None, str, str | None] | None:
        record = self._find_runtime_or_legacy_record(db, record_id)
        if not record:
            return None
        return record.project_id, self._record_template_id(record), record.status, self._record_approval_snapshot(record)

    def _find_runtime_or_legacy_record(self, db: Session, record_id: str):
        runtime = db.query(RuntimeRecord).filter(RuntimeRecord.id == record_id).first()
        if runtime:
            return runtime
        return db.query(Record).filter(Record.id == record_id).first()

    def _validate_transition(self, db: Session, payload: ReviewActionCreate, from_status: str | None, template_id: str | None, snapshot_json: str | None = None) -> None:
        if from_status is None:
            raise ValueError("El registro no tiene estado actual")
        if from_status == "corrected" and payload.to_status == "submitted":
            return  # El responsable reenvía; los pasos de aprobación empiezan de nuevo.
        configured_actions = approval_flow_service.next_actions(db, payload.project_id, template_id, from_status, snapshot_json)
        configured_targets = {item.to_status for item in configured_actions if item.source == "configured"}
        if configured_targets:
            if payload.to_status not in configured_targets:
                raise ValueError(f"Transicion no permitida por flujo configurado: {from_status} -> {payload.to_status}")
            return
        allowed = ALLOWED_TRANSITIONS.get(from_status)
        if allowed is None:
            raise ValueError(f"Estado actual no soportado: {from_status}")
        if payload.to_status not in allowed:
            raise ValueError(f"Transicion no permitida: {from_status} -> {payload.to_status}")

    def _should_advance_configured_step(self, db: Session, payload: ReviewActionCreate, user_id: str, from_status: str | None, configured_step: Any | None) -> bool:
        if not configured_step or configured_step.require_all != "true":
            return True
        if from_status is None:
            raise ValueError("El registro no tiene estado actual")
        required_user_ids = approval_flow_service.required_approver_user_ids(db, payload.project_id, configured_step)
        if not required_user_ids:
            return True
        if user_id not in required_user_ids:
            raise ValueError("Usuario no requerido para esta aprobacion multiple")
        last_return = db.query(ReviewAction.created_at).filter(ReviewAction.record_id == payload.record_id, ReviewAction.to_status == "returned").order_by(ReviewAction.created_at.desc()).first()
        cycle_start = last_return[0] if last_return else None
        actions_query = db.query(ReviewAction).filter(
            ReviewAction.record_id == payload.record_id,
            ReviewAction.from_status == from_status,
            ReviewAction.to_status == payload.to_status,
            ReviewAction.action == payload.action,
        )
        if cycle_start is not None:
            actions_query = actions_query.filter(ReviewAction.created_at > cycle_start)
        existing_for_user = actions_query.filter(ReviewAction.user_id == user_id).first()
        if existing_for_user:
            raise ValueError("Aprobacion ya registrada para este usuario")
        completed_user_ids = {
            row[0]
            for row in actions_query.with_entities(ReviewAction.user_id).filter(ReviewAction.user_id.in_(required_user_ids)).all()
        }
        completed_user_ids.add(user_id)
        return required_user_ids.issubset(completed_user_ids)

    def _configured_step_flow_version(self, db: Session, configured_step: Any | None) -> int | None:
        if not configured_step:
            return None
        if hasattr(configured_step, "flow_version") and configured_step.flow_version is not None:
            return int(configured_step.flow_version)
        from app.models.approval_flow import ApprovalFlow

        flow = db.get(ApprovalFlow, configured_step.flow_id)
        return flow.flow_version if flow else None

    def _add_status_notification(self, db: Session, record: RuntimeRecord | Record, payload: ReviewActionCreate, from_status: str, actor_id: str) -> None:
        recipient_id = self._record_owner_id(record)
        if not recipient_id or recipient_id == actor_id:
            return
        if not self._active_project_user(db, recipient_id, payload.project_id):
            return

        subject = f"Registro {payload.to_status}"
        body = (
            f"El registro {payload.record_id} cambió de {from_status} a {payload.to_status} "
            f"por la acción {payload.action}."
        )
        if payload.notes:
            body = f"{body}\n\nObservación: {payload.notes}"

        db.add(InternalMessage(
            project_id=payload.project_id,
            sender_id=actor_id,
            recipient_id=recipient_id,
            subject=subject,
            body=body,
            status="unread",
        ))

        # Notificacion WhatsApp solo ante rechazo/devolucion (ver 4.4 de la
        # especificacion original: "ante un rechazo, envia automaticamente
        # notificaciones por WhatsApp"). El "Enlace Magico" original asume una
        # app movil nativa con esquema infomatt://; como el sistema real es
        # web/PWA/escritorio, se adapta a un enlace HTTPS real hacia la
        # pantalla de registros -- y, si el revisor indico el campo puntual
        # con el error (payload.rejected_field_name), el enlace apunta
        # directo a ese registro y ese campo (?recordId=X&campo=Y), no solo
        # a la pantalla general. No interrumpe el flujo si WAHA no esta
        # configurado o falla (ver whatsapp_service.send_text).
        if payload.to_status in {"rejected", "returned"}:
            recipient = db.query(User).filter(User.id == recipient_id).first()
            if recipient and recipient.phone:
                template_id = self._record_template_id(record)
                base_path = f"/records/{template_id}" if template_id else "/records"
                magic_link = f"{settings.frontend_url.rstrip('/')}{base_path}?recordId={payload.record_id}"
                if payload.rejected_field_name:
                    magic_link = f"{magic_link}&campo={quote(payload.rejected_field_name)}"
                    whatsapp_message = f"{body}\n\nCampo a corregir: {payload.rejected_field_name}\nCorrige aqui: {magic_link}"
                else:
                    whatsapp_message = f"{body}\n\nCorrige aqui: {magic_link}"
                whatsapp_service.send_text(
                    db,
                    project_id=payload.project_id,
                    recipient_phone=recipient.phone,
                    recipient_user_id=recipient_id,
                    reference_record_id=payload.record_id,
                    message=whatsapp_message,
                )

    def _record_owner_id(self, record: RuntimeRecord | Record) -> str | None:
        if isinstance(record, RuntimeRecord):
            return record.submitted_by
        return record.created_by

    def _record_template_id(self, record: RuntimeRecord | Record) -> str | None:
        if isinstance(record, RuntimeRecord):
            return record.template_id
        return record.form_id

    def _record_approval_snapshot(self, record: RuntimeRecord | Record) -> str | None:
        if isinstance(record, RuntimeRecord):
            return record.approval_flow_snapshot_json
        return None

    def _active_project_user(self, db: Session, user_id: str, project_id: str) -> bool:
        return db.query(UserProjectAssignment).join(User, User.id == UserProjectAssignment.user_id).filter(
            UserProjectAssignment.user_id == user_id,
            UserProjectAssignment.project_id == project_id,
            UserProjectAssignment.status == "active",
            User.status == "active",
        ).first() is not None


review_service = ReviewService()
