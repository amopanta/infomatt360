"""Purga controlada de entornos (Tenant Clean).

Reinterpretacion del "TRUNCATE sobre el esquema aislado de la organizacion"
de la especificacion original para nuestro modelo de tenant logico (ver
docs/71_ORGANIZACIONES_TENANT_LOGICO.md): en vez de un schema fisico por
tenant, se borran por `project_id` las filas de datos operativos/de prueba
de cada proyecto que pertenece a la organizacion, dejando intactas las
tablas de identidad (usuarios, asignaciones) y de configuracion/maestros
(inventario ERP, plantillas, integraciones, storage, etc.), tal como pide
la especificacion ("protegiendo las tablas de inventarios maestros y
usuarios"). El modulo ERP completo (`ErpInventoryItem`, `ErpInventoryMovement`,
`ErpPayrollEntry`) y el ledger de integraciones (`IntegrationJob`) quedan
fuera de la purga: sus propios modelos se documentan como "ledger
inmutable" (nunca se edita ni se borra una fila existente), asi que
tenant-clean respeta esa invariante en vez de romperla.

Accion critica: se exige un permiso dedicado (`organizations.tenant_clean`),
un codigo TOTP vigente del usuario que la ejecuta, y que el usuario escriba
el slug exacto de la organizacion como confirmacion explicita.
"""

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models.ai import AiCheck, ExecutiveAnalysis, OcrResult
from app.models.bulk_import import BulkImportJob
from app.models.enrollment import ManagerQrToken
from app.models.excel_import import ExcelImportJob
from app.models.files import FileAsset
from app.models.identity import Project
from app.models.messages import InternalMessage
from app.models.participants import Participant
from app.models.review import ReviewAction
from app.models.runtime_record import RuntimeRecord, RuntimeRecordValue
from app.models.whatsapp import WhatsAppNotification

# Modelos con project_id que se consideran "datos de prueba/operativos" y se
# purgan. No incluye: User, UserProjectAssignment, Role, Project, Organization,
# OrganizationBranding, BuilderTemplate, ApprovalFlow/Step, IntegrationSource/
# Map, IntegrationJob, ErpInventoryItem, ErpInventoryMovement,
# ErpPayrollEntry, ErpTemplateConfig, MailProfile, StorageProfile, ApiKey,
# AiAuditConfig, AuditLog, ScheduledTask, ReportDefinition, FormTheme.
PURGEABLE_MODELS = [
    Participant,
    FileAsset,
    AiCheck,
    OcrResult,
    ExecutiveAnalysis,
    ReviewAction,
    InternalMessage,
    WhatsAppNotification,
    ExcelImportJob,
    BulkImportJob,
    ManagerQrToken,
]


class GovernanceService:
    def get_organization_project_ids(self, db: Session, organization_id: str) -> list[str]:
        rows = db.query(Project.id).filter(Project.organization_id == organization_id).all()
        return [row[0] for row in rows]

    def tenant_clean(self, db: Session, organization_id: str) -> dict[str, object]:
        project_ids = self.get_organization_project_ids(db, organization_id)
        deleted_counts: dict[str, int] = {}

        if project_ids:
            record_ids = [row[0] for row in db.query(RuntimeRecord.id).filter(RuntimeRecord.project_id.in_(project_ids)).all()]
            if record_ids:
                result = db.execute(delete(RuntimeRecordValue).where(RuntimeRecordValue.record_id.in_(record_ids)))
                deleted_counts["runtime_record_values"] = result.rowcount or 0

            result = db.execute(delete(RuntimeRecord).where(RuntimeRecord.project_id.in_(project_ids)))
            deleted_counts["runtime_records"] = result.rowcount or 0

            for model in PURGEABLE_MODELS:
                result = db.execute(delete(model).where(model.project_id.in_(project_ids)))
                deleted_counts[model.__tablename__] = result.rowcount or 0

            db.commit()

        return {"organization_id": organization_id, "projects_purged": project_ids, "deleted_counts": deleted_counts}


governance_service = GovernanceService()
