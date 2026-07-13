from fastapi import APIRouter

from app.api.v1.acta import router as acta_router
from app.api.v1.ai import router as ai_router
from app.api.v1.ai_audit import router as ai_audit_router
from app.api.v1.api_keys import router as api_keys_router
from app.api.v1.approval_flows import router as approval_flows_router
from app.api.v1.assignments import router as assignments_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.backups import router as backups_router
from app.api.v1.builder import router as builder_router
from app.api.v1.builder_layout import router as builder_layout_router
from app.api.v1.compiler import router as compiler_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.emergency_access import router as emergency_access_router
from app.api.v1.enrollment import router as enrollment_router
from app.api.v1.erp import router as erp_router
from app.api.v1.etl import router as etl_router
from app.api.v1.excel_import import router as excel_import_router
from app.api.v1.external_api import router as external_api_router
from app.api.v1.external_data import router as external_data_router
from app.api.v1.files import router as files_router
from app.api.v1.forms import router as forms_router
from app.api.v1.gis import router as gis_router
from app.api.v1.health import router as health_router
from app.api.v1.identity import router as identity_router
from app.api.v1.install import router as install_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.messages import router as messages_router
from app.api.v1.mirror import router as mirror_router
from app.api.v1.organizations import router as organizations_router
from app.api.v1.participants import router as participants_router
from app.api.v1.project_context import router as project_context_router
from app.api.v1.public import router as public_router
from app.api.v1.public_forms import router as public_forms_router
from app.api.v1.records import router as records_router
from app.api.v1.reports import router as reports_router
from app.api.v1.review import router as review_router
from app.api.v1.runtime import router as runtime_router
from app.api.v1.scheduler import router as scheduler_router
from app.api.v1.security import router as security_router
from app.api.v1.storage import router as storage_router
from app.api.v1.support import router as support_router
from app.api.v1.whatsapp import router as whatsapp_router
from app.api.v1.xlsform import router as xlsform_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
api_v1_router.include_router(public_router, prefix="/public", tags=["public"])
api_v1_router.include_router(install_router, prefix="/install", tags=["install"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(security_router, prefix="/security", tags=["security"])
api_v1_router.include_router(api_keys_router, prefix="/api-keys", tags=["api-keys"])
api_v1_router.include_router(dashboard_router, prefix="/dashboard", tags=["dashboard"])
api_v1_router.include_router(identity_router, prefix="/identity", tags=["identity"])
api_v1_router.include_router(organizations_router, prefix="/organizations", tags=["organizations"])
api_v1_router.include_router(backups_router, prefix="/backups", tags=["backups"])
api_v1_router.include_router(assignments_router, prefix="/assignments", tags=["assignments"])
api_v1_router.include_router(enrollment_router, prefix="/enrollment", tags=["enrollment"])
api_v1_router.include_router(emergency_access_router, prefix="/emergency-access", tags=["emergency-access"])
api_v1_router.include_router(support_router, prefix="/support", tags=["support"])
api_v1_router.include_router(project_context_router, prefix="/projects", tags=["project-context"])
api_v1_router.include_router(forms_router, prefix="/forms", tags=["forms"])
api_v1_router.include_router(participants_router, prefix="/participants", tags=["participants"])
api_v1_router.include_router(excel_import_router, prefix="/excel-import", tags=["excel-import"])
api_v1_router.include_router(records_router, prefix="/records", tags=["records"])
api_v1_router.include_router(files_router, prefix="/files", tags=["files"])
api_v1_router.include_router(storage_router, prefix="/storage", tags=["storage"])
api_v1_router.include_router(messages_router, prefix="/messages", tags=["messages"])
api_v1_router.include_router(review_router, prefix="/review", tags=["review"])
api_v1_router.include_router(approval_flows_router, prefix="/approval-flows", tags=["approval-flows"])
api_v1_router.include_router(audit_router, prefix="/audit", tags=["audit"])
api_v1_router.include_router(integrations_router, prefix="/integrations", tags=["integrations"])
api_v1_router.include_router(etl_router, prefix="/etl", tags=["etl"])
api_v1_router.include_router(external_data_router, prefix="/external-data", tags=["external-data"])
api_v1_router.include_router(external_api_router, prefix="/external-api", tags=["external-api"])
api_v1_router.include_router(mirror_router, prefix="/mirror", tags=["mirror"])
api_v1_router.include_router(scheduler_router, prefix="/scheduler", tags=["scheduler"])
api_v1_router.include_router(reports_router, prefix="/reports", tags=["reports"])
api_v1_router.include_router(acta_router, prefix="/acta-templates", tags=["acta"])
api_v1_router.include_router(ai_router, prefix="/ai", tags=["ai"])
api_v1_router.include_router(ai_audit_router, prefix="/ai-audit", tags=["ai-audit"])
api_v1_router.include_router(gis_router, prefix="/gis", tags=["gis"])
api_v1_router.include_router(builder_router, prefix="/builder", tags=["builder"])
api_v1_router.include_router(builder_layout_router, prefix="/builder", tags=["builder-layout"])
api_v1_router.include_router(xlsform_router, prefix="/xlsform", tags=["xlsform"])
api_v1_router.include_router(erp_router, prefix="/erp", tags=["erp"])
api_v1_router.include_router(whatsapp_router, prefix="/whatsapp", tags=["whatsapp"])
api_v1_router.include_router(runtime_router, prefix="/runtime", tags=["runtime"])
api_v1_router.include_router(public_forms_router, prefix="/public-forms", tags=["public-forms"])
api_v1_router.include_router(compiler_router, prefix="/compiler", tags=["compiler"])
