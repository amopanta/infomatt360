from sqlalchemy.orm import Session

from app.models.mirror import MirrorPlan, MirrorTarget
from app.schemas.mirror import MirrorPlanCreate, MirrorPlanRead, MirrorTargetCreate, MirrorTargetRead


def target_to_read(row: MirrorTarget) -> MirrorTargetRead:
    return MirrorTargetRead(id=row.id, project_id=row.project_id, name=row.name, engine=row.engine, conn_json=row.conn_json, status=row.status)


def plan_to_read(row: MirrorPlan) -> MirrorPlanRead:
    return MirrorPlanRead(id=row.id, target_id=row.target_id, name=row.name, tables_json=row.tables_json, schedule_mode=row.schedule_mode, status=row.status, last_result=row.last_result)


class MirrorService:
    def create_target(self, db: Session, payload: MirrorTargetCreate) -> MirrorTargetRead:
        row = MirrorTarget(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return target_to_read(row)

    def list_targets(self, db: Session, project_id: str) -> list[MirrorTargetRead]:
        rows = db.query(MirrorTarget).filter(MirrorTarget.project_id == project_id).order_by(MirrorTarget.created_at.desc()).all()
        return [target_to_read(row) for row in rows]

    def create_plan(self, db: Session, payload: MirrorPlanCreate) -> MirrorPlanRead:
        row = MirrorPlan(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return plan_to_read(row)

    def list_plans(self, db: Session, target_id: str) -> list[MirrorPlanRead]:
        rows = db.query(MirrorPlan).filter(MirrorPlan.target_id == target_id).order_by(MirrorPlan.created_at.desc()).all()
        return [plan_to_read(row) for row in rows]


mirror_service = MirrorService()
