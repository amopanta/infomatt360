from sqlalchemy.orm import Session

from app.models.ai import AiCheck, ExecutiveAnalysis, OcrResult
from app.schemas.ai import AiCheckCreate, AiCheckRead, ExecutiveAnalysisCreate, ExecutiveAnalysisRead, OcrResultCreate, OcrResultRead


def check_to_read(row: AiCheck) -> AiCheckRead:
    return AiCheckRead(id=row.id, project_id=row.project_id, record_id=row.record_id, file_id=row.file_id, check_type=row.check_type, status=row.status, result_json=row.result_json, created_by=row.created_by)


def ocr_to_read(row: OcrResult) -> OcrResultRead:
    return OcrResultRead(id=row.id, project_id=row.project_id, file_id=row.file_id, text_result=row.text_result, metadata_json=row.metadata_json, status=row.status)


def analysis_to_read(row: ExecutiveAnalysis) -> ExecutiveAnalysisRead:
    return ExecutiveAnalysisRead(id=row.id, project_id=row.project_id, source_type=row.source_type, source_id=row.source_id, summary_text=row.summary_text, metrics_json=row.metrics_json, status=row.status, created_by=row.created_by)


class AiService:
    def create_check(self, db: Session, payload: AiCheckCreate, user_id: str) -> AiCheckRead:
        row = AiCheck(**payload.model_dump(), created_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return check_to_read(row)

    def list_checks(self, db: Session, project_id: str) -> list[AiCheckRead]:
        rows = db.query(AiCheck).filter(AiCheck.project_id == project_id).order_by(AiCheck.created_at.desc()).all()
        return [check_to_read(row) for row in rows]

    def create_ocr(self, db: Session, payload: OcrResultCreate) -> OcrResultRead:
        row = OcrResult(**payload.model_dump())
        db.add(row)
        db.commit()
        db.refresh(row)
        return ocr_to_read(row)

    def create_analysis(self, db: Session, payload: ExecutiveAnalysisCreate, user_id: str) -> ExecutiveAnalysisRead:
        row = ExecutiveAnalysis(**payload.model_dump(), created_by=user_id)
        db.add(row)
        db.commit()
        db.refresh(row)
        return analysis_to_read(row)


ai_service = AiService()
