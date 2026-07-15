import json
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import Session

from app.api.permissions import get_project_permissions
from app.models.approval_flow import ApprovalFlow, ApprovalFlowStep
from app.models.assignment import UserProjectAssignment
from app.models.identity import User
from app.models.review import ReviewAction
from app.schemas.approval_flow import (
    ApprovalFlowCreate,
    ApprovalFlowDetail,
    ApprovalFlowRead,
    ApprovalFlowStepCreate,
    ApprovalFlowStepRead,
    ApprovalFlowStepUpdate,
    ApprovalFlowUpdate,
    ReviewApprovalProgress,
    ReviewFlowComparison,
    ReviewFlowSnapshot,
    ReviewFlowSnapshotStep,
    ReviewNextAction,
)


def flow_to_read(row: ApprovalFlow) -> ApprovalFlowRead:
    return ApprovalFlowRead(
        id=row.id,
        project_id=row.project_id,
        template_id=row.template_id,
        name=row.name,
        description=row.description,
        flow_version=row.flow_version,
        status=row.status,
        created_at=row.created_at,
    )


def step_to_read(row: ApprovalFlowStep) -> ApprovalFlowStepRead:
    return ApprovalFlowStepRead(
        id=row.id,
        flow_id=row.flow_id,
        step_order=row.step_order,
        name=row.name,
        action_label=row.action_label,
        action=row.action,
        status_after=row.status_after,
        required_permission=row.required_permission,
        approver_user_id=row.approver_user_id,
        approver_role_id=row.approver_role_id,
        require_all=row.require_all == "true",
        status=row.status,
        created_at=row.created_at,
    )


# "Anular" (ver docs/100) se ofrece en todo estado no terminal, igual que en
# el REVIEW_ACTIONS del frontend (RecordsApp.tsx) -- debe declararse aqui
# tambien porque next_actions() devuelve DEFAULT_ACTIONS cuando el proyecto
# no tiene un flujo de aprobacion configurado (el caso comun/por defecto), y
# esa lista reemplaza por completo al fallback del frontend en cuanto no
# viene vacia (ver RecordsApp.tsx: `actions = nextActions.length ? ... :
# fallbackActions`). Omitir "voided" aqui lo dejaba inalcanzable desde la UI
# para cualquier registro sin flujo configurado -- solo se detecto probando
# en el navegador real, no con las pruebas unitarias que llaman la API
# directo con to_status="voided".
VOID_ACTION = ReviewNextAction(label="Anular", to_status="voided", action="void", required_permission="records.void")

DEFAULT_ACTIONS: dict[str, list[ReviewNextAction]] = {
    "draft": [
        ReviewNextAction(label="Enviar", to_status="submitted", action="submit"),
        ReviewNextAction(label="Cancelar", to_status="cancelled", action="cancel"),
    ],
    "submitted": [
        ReviewNextAction(label="Iniciar revisión", to_status="under_review", action="start_review", required_permission="records.review"),
        ReviewNextAction(label="Aprobar", to_status="approved", action="approve", required_permission="records.approve"),
        ReviewNextAction(label="Devolver", to_status="returned", action="return", required_permission="records.review"),
        ReviewNextAction(label="Rechazar", to_status="rejected", action="reject", required_permission="records.approve"),
        VOID_ACTION,
    ],
    "under_review": [
        ReviewNextAction(label="Aprobación técnica", to_status="tech_approved", action="technical_approve", required_permission="records.review"),
        ReviewNextAction(label="Aprobar", to_status="approved", action="approve", required_permission="records.approve"),
        ReviewNextAction(label="Devolver", to_status="returned", action="return", required_permission="records.review"),
        ReviewNextAction(label="Rechazar", to_status="rejected", action="reject", required_permission="records.approve"),
        VOID_ACTION,
    ],
    "tech_approved": [
        ReviewNextAction(label="Aprobación coordinador", to_status="coordinator_approved", action="coordinator_approve", required_permission="records.coordinate"),
        ReviewNextAction(label="Aprobar final", to_status="approved", action="approve", required_permission="records.approve"),
        ReviewNextAction(label="Devolver", to_status="returned", action="return", required_permission="records.review"),
        ReviewNextAction(label="Rechazar", to_status="rejected", action="reject", required_permission="records.approve"),
        VOID_ACTION,
    ],
    "coordinator_approved": [
        ReviewNextAction(label="Aprobar final", to_status="approved", action="final_approve", required_permission="records.approve"),
        ReviewNextAction(label="Devolver", to_status="returned", action="return", required_permission="records.review"),
        ReviewNextAction(label="Rechazar", to_status="rejected", action="reject", required_permission="records.approve"),
        VOID_ACTION,
    ],
    "returned": [
        ReviewNextAction(label="Marcar corregido", to_status="corrected", action="mark_corrected"),
        VOID_ACTION,
    ],
    "corrected": [
        ReviewNextAction(label="Reenviar a revisión", to_status="under_review", action="resubmit_review", required_permission="records.review"),
        VOID_ACTION,
    ],
    "approved": [
        ReviewNextAction(label="Archivar", to_status="archived", action="archive", required_permission="records.approve"),
        ReviewNextAction(label="Marcar sincronizado", to_status="synced", action="mark_synced", required_permission="records.approve"),
        VOID_ACTION,
    ],
    "rejected": [
        ReviewNextAction(label="Archivar", to_status="archived", action="archive", required_permission="records.approve"),
        VOID_ACTION,
    ],
    "archived": [VOID_ACTION],
    "synced": [
        ReviewNextAction(label="Archivar", to_status="archived", action="archive", required_permission="records.approve"),
        VOID_ACTION,
    ],
}


class ApprovalFlowService:
    def snapshot_for_record(self, db: Session, project_id: str, template_id: str | None) -> tuple[str | None, str | None, str | None]:
        flow = self.get_active_flow(db, project_id, template_id)
        if not flow:
            return None, None, None
        steps = db.query(ApprovalFlowStep).filter(
            ApprovalFlowStep.flow_id == flow.id,
            ApprovalFlowStep.status == "active",
        ).order_by(ApprovalFlowStep.step_order.asc()).all()
        snapshot = {
            "flow_id": flow.id,
            "flow_version": flow.flow_version,
            "name": flow.name,
            "template_id": flow.template_id,
            "steps": [
                {
                    "id": step.id,
                    "flow_id": step.flow_id,
                    "step_order": step.step_order,
                    "name": step.name,
                    "action_label": step.action_label,
                    "action": step.action,
                    "status_after": step.status_after,
                    "required_permission": step.required_permission,
                    "approver_user_id": step.approver_user_id,
                    "approver_role_id": step.approver_role_id,
                    "require_all": step.require_all,
                    "status": step.status,
                }
                for step in steps
            ],
        }
        return flow.id, str(flow.flow_version), json.dumps(snapshot, ensure_ascii=False)

    def flow_comparison(self, db: Session, project_id: str, template_id: str | None, snapshot_json: str | None) -> ReviewFlowComparison:
        snapshot = self._snapshot_read(snapshot_json)
        _current_flow_id, _current_version, current_json = self.snapshot_for_record(db, project_id, template_id)
        current = self._snapshot_read(current_json)
        differences = self._snapshot_differences(snapshot, current)
        return ReviewFlowComparison(
            has_snapshot=snapshot is not None,
            changed=bool(differences),
            differences=differences,
            snapshot=snapshot,
            current=current,
        )

    def create_flow(self, db: Session, payload: ApprovalFlowCreate) -> ApprovalFlowRead:
        row = ApprovalFlow(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return flow_to_read(row)

    def update_flow(self, db: Session, flow: ApprovalFlow, payload: ApprovalFlowUpdate) -> ApprovalFlowRead:
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(flow, field, value)
        flow.flow_version += 1
        db.add(flow)
        db.commit()
        db.refresh(flow)
        return flow_to_read(flow)

    def list_flows(self, db: Session, project_id: str, template_id: str | None = None) -> list[ApprovalFlowRead]:
        query = db.query(ApprovalFlow).filter(ApprovalFlow.project_id == project_id)
        if template_id is not None:
            query = query.filter(ApprovalFlow.template_id == template_id)
        rows = query.order_by(ApprovalFlow.created_at.desc()).all()
        return [flow_to_read(row) for row in rows]

    def add_step(self, db: Session, payload: ApprovalFlowStepCreate) -> ApprovalFlowStepRead:
        row = ApprovalFlowStep(
            **{
                **payload.model_dump(exclude={"require_all"}),
                "require_all": "true" if payload.require_all else "false",
            }
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return step_to_read(row)

    def update_step(self, db: Session, step: ApprovalFlowStep, payload: ApprovalFlowStepUpdate) -> ApprovalFlowStepRead:
        for field, value in payload.model_dump(exclude_unset=True, exclude={"require_all"}).items():
            setattr(step, field, value)
        if payload.require_all is not None:
            step.require_all = "true" if payload.require_all else "false"
        flow = db.get(ApprovalFlow, step.flow_id)
        if flow:
            flow.flow_version += 1
            db.add(flow)
        db.add(step)
        db.commit()
        db.refresh(step)
        return step_to_read(step)

    def detail(self, db: Session, flow_id: str) -> ApprovalFlowDetail | None:
        flow = db.get(ApprovalFlow, flow_id)
        if not flow:
            return None
        steps = db.query(ApprovalFlowStep).filter(ApprovalFlowStep.flow_id == flow.id).order_by(ApprovalFlowStep.step_order.asc()).all()
        return ApprovalFlowDetail(**flow_to_read(flow).model_dump(), steps=[step_to_read(step) for step in steps])

    def get_active_flow(self, db: Session, project_id: str, template_id: str | None = None) -> ApprovalFlow | None:
        if template_id:
            flow = db.query(ApprovalFlow).filter(
                ApprovalFlow.project_id == project_id,
                ApprovalFlow.template_id == template_id,
                ApprovalFlow.status == "active",
            ).order_by(ApprovalFlow.created_at.desc()).first()
            if flow:
                return flow
        return db.query(ApprovalFlow).filter(
            ApprovalFlow.project_id == project_id,
            ApprovalFlow.template_id.is_(None),
            ApprovalFlow.status == "active",
        ).order_by(ApprovalFlow.created_at.desc()).first()

    def next_actions(self, db: Session, project_id: str, template_id: str | None, current_status: str, snapshot_json: str | None = None) -> list[ReviewNextAction]:
        steps = self._steps_from_snapshot(snapshot_json)
        if not steps:
            flow = self.get_active_flow(db, project_id, template_id)
            if not flow:
                return DEFAULT_ACTIONS.get(current_status, [])
            steps = db.query(ApprovalFlowStep).filter(
                ApprovalFlowStep.flow_id == flow.id,
                ApprovalFlowStep.status == "active",
            ).order_by(ApprovalFlowStep.step_order.asc()).all()
        next_step = self._next_configured_step(current_status, steps)
        if not next_step:
            return DEFAULT_ACTIONS.get(current_status, [])
        configured_action = ReviewNextAction(
            label=next_step.action_label,
            to_status=next_step.status_after,
            action=next_step.action,
            required_permission=next_step.required_permission,
            source="configured",
        )
        # "Anular" (ver docs/100) es una invalidacion administrativa, no un
        # paso mas del flujo de aprobacion -- debe seguir disponible aunque
        # el flujo configurado por el proyecto no la incluya explicitamente,
        # igual que en el camino sin flujo (DEFAULT_ACTIONS). No aplica a los
        # estados ya terminales.
        if current_status not in ("draft", "cancelled", "voided"):
            return [configured_action, VOID_ACTION]
        return [configured_action]

    def approval_progress(self, db: Session, project_id: str, template_id: str | None, current_status: str, record_id: str, snapshot_json: str | None = None) -> list[ReviewApprovalProgress]:
        steps = self._steps_from_snapshot(snapshot_json)
        if not steps:
            flow = self.get_active_flow(db, project_id, template_id)
            if not flow:
                return []
            steps = db.query(ApprovalFlowStep).filter(
                ApprovalFlowStep.flow_id == flow.id,
                ApprovalFlowStep.status == "active",
            ).order_by(ApprovalFlowStep.step_order.asc()).all()
        next_step = self._next_configured_step(current_status, steps)
        if not next_step or next_step.require_all != "true":
            return []
        required_user_ids = self.required_approver_user_ids(db, project_id, next_step)
        if not required_user_ids:
            return []
        approved_user_ids = {
            row[0]
            for row in db.query(ReviewAction.user_id).filter(
                ReviewAction.record_id == record_id,
                ReviewAction.from_status == current_status,
                ReviewAction.to_status == next_step.status_after,
                ReviewAction.action == next_step.action,
                ReviewAction.user_id.in_(required_user_ids),
            ).all()
        }
        pending_user_ids = required_user_ids - approved_user_ids
        return [ReviewApprovalProgress(
            label=next_step.action_label,
            to_status=next_step.status_after,
            action=next_step.action,
            required_count=len(required_user_ids),
            approved_count=len(approved_user_ids),
            pending_count=len(pending_user_ids),
            approved_user_ids=sorted(approved_user_ids),
            pending_user_ids=sorted(pending_user_ids),
        )]

    def find_step_for_status(self, db: Session, project_id: str, template_id: str | None, to_status: str, snapshot_json: str | None = None) -> Any | None:
        steps = self._steps_from_snapshot(snapshot_json)
        if steps:
            for step in steps:
                if step.status_after == to_status and step.status == "active":
                    return step
            return None
        flow = self.get_active_flow(db, project_id, template_id)
        if not flow:
            return None
        return db.query(ApprovalFlowStep).filter(
            ApprovalFlowStep.flow_id == flow.id,
            ApprovalFlowStep.status_after == to_status,
            ApprovalFlowStep.status == "active",
        ).first()

    def user_can_execute_step(self, db: Session, user_id: str, project_id: str, step: Any) -> bool:
        assignment, permissions = get_project_permissions(db, user_id, project_id)
        if not assignment or step.required_permission not in permissions:
            return False
        if step.approver_user_id and step.approver_user_id != user_id:
            return False
        if step.approver_role_id and step.approver_role_id != assignment.role_id:
            return False
        return True

    def required_approver_user_ids(self, db: Session, project_id: str, step: Any) -> set[str]:
        if step.approver_user_id:
            return {step.approver_user_id}
        if not step.approver_role_id:
            return set()
        rows = db.query(UserProjectAssignment.user_id).join(User, User.id == UserProjectAssignment.user_id).filter(
            UserProjectAssignment.project_id == project_id,
            UserProjectAssignment.role_id == step.approver_role_id,
            UserProjectAssignment.status == "active",
            User.status == "active",
        ).all()
        return {row[0] for row in rows}

    def _next_configured_step(self, current_status: str, steps: list[Any]) -> Any | None:
        if current_status in {"submitted", "under_review", "corrected"}:
            return steps[0] if steps else None
        for index, step in enumerate(steps):
            if step.status_after == current_status:
                return steps[index + 1] if index + 1 < len(steps) else None
        return None

    def _steps_from_snapshot(self, snapshot_json: str | None) -> list[Any]:
        if not snapshot_json:
            return []
        try:
            snapshot = json.loads(snapshot_json)
        except json.JSONDecodeError:
            return []
        steps = snapshot.get("steps", [])
        if not isinstance(steps, list):
            return []
        return [
            SimpleNamespace(
                id=item.get("id"),
                flow_id=item.get("flow_id") or snapshot.get("flow_id"),
                step_order=item.get("step_order", 0),
                name=item.get("name", ""),
                action_label=item.get("action_label", ""),
                action=item.get("action", ""),
                status_after=item.get("status_after", ""),
                required_permission=item.get("required_permission", ""),
                approver_user_id=item.get("approver_user_id"),
                approver_role_id=item.get("approver_role_id"),
                require_all=item.get("require_all", "false"),
                status=item.get("status", "active"),
                flow_version=snapshot.get("flow_version"),
            )
            for item in steps
            if isinstance(item, dict)
        ]

    def _snapshot_read(self, snapshot_json: str | None) -> ReviewFlowSnapshot | None:
        if not snapshot_json:
            return None
        try:
            snapshot = json.loads(snapshot_json)
        except json.JSONDecodeError:
            return None
        steps = snapshot.get("steps", [])
        if not isinstance(steps, list):
            steps = []
        return ReviewFlowSnapshot(
            flow_id=snapshot.get("flow_id"),
            flow_version=str(snapshot.get("flow_version")) if snapshot.get("flow_version") is not None else None,
            name=snapshot.get("name"),
            template_id=snapshot.get("template_id"),
            steps=[
                ReviewFlowSnapshotStep(
                    step_order=int(item.get("step_order") or 0),
                    name=item.get("name") or "",
                    action_label=item.get("action_label") or "",
                    action=item.get("action") or "",
                    status_after=item.get("status_after") or "",
                    required_permission=item.get("required_permission") or "",
                    approver_user_id=item.get("approver_user_id"),
                    approver_role_id=item.get("approver_role_id"),
                    require_all=item.get("require_all") in {True, "true", "True", "1", 1},
                    status=item.get("status") or "active",
                )
                for item in steps
                if isinstance(item, dict)
            ],
        )

    def _snapshot_differences(self, snapshot: ReviewFlowSnapshot | None, current: ReviewFlowSnapshot | None) -> list[str]:
        if not snapshot and not current:
            return []
        if snapshot and not current:
            return ["El flujo actual ya no existe o no está activo."]
        if current and not snapshot:
            return ["El registro no tiene snapshot histórico."]
        assert snapshot is not None and current is not None
        differences: list[str] = []
        if snapshot.flow_id != current.flow_id:
            differences.append(f"Cambió el flujo: {snapshot.flow_id or '—'} → {current.flow_id or '—'}")
        if snapshot.flow_version != current.flow_version:
            differences.append(f"Cambió la versión: {snapshot.flow_version or '—'} → {current.flow_version or '—'}")
        if snapshot.name != current.name:
            differences.append(f"Cambió el nombre: {snapshot.name or '—'} → {current.name or '—'}")
        if len(snapshot.steps) != len(current.steps):
            differences.append(f"Cambió la cantidad de pasos: {len(snapshot.steps)} → {len(current.steps)}")
        snapshot_steps = {step.step_order: step for step in snapshot.steps}
        current_steps = {step.step_order: step for step in current.steps}
        for order in sorted(set(snapshot_steps) | set(current_steps)):
            old = snapshot_steps.get(order)
            new = current_steps.get(order)
            if old and not new:
                differences.append(f"Paso {order} fue eliminado del flujo actual.")
                continue
            if new and not old:
                differences.append(f"Paso {order} fue agregado al flujo actual.")
                continue
            if not old or not new:
                continue
            for field, label in [
                ("name", "nombre"),
                ("action_label", "botón"),
                ("action", "acción"),
                ("status_after", "estado destino"),
                ("required_permission", "permiso"),
                ("approver_user_id", "usuario aprobador"),
                ("approver_role_id", "rol aprobador"),
                ("require_all", "require_all"),
                ("status", "estado"),
            ]:
                old_value = getattr(old, field)
                new_value = getattr(new, field)
                if old_value != new_value:
                    differences.append(f"Paso {order}: cambió {label}: {old_value or '—'} → {new_value or '—'}")
        return differences


approval_flow_service = ApprovalFlowService()
