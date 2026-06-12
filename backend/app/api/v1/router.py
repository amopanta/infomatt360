from fastapi import APIRouter

from app.api.v1.assignments import router as assignments_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.files import router as files_router
from app.api.v1.forms import router as forms_router
from app.api.v1.health import router as health_router
from app.api.v1.identity import router as identity_router
from app.api.v1.messages import router as messages_router
from app.api.v1.participants import router as participants_router
from app.api.v1.project_context import router as project_context_router
from app.api.v1.records import router as records_router
from app.api.v1.review import router as review_router
from app.api.v1.security import router as security_router
from app.api.v1.storage import router as storage_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(security_router, prefix="/security", tags=["security"])
api_v1_router.include_router(identity_router, prefix="/identity", tags=["identity"])
api_v1_router.include_router(assignments_router, prefix="/assignments", tags=["assignments"])
api_v1_router.include_router(project_context_router, prefix="/projects", tags=["project-context"])
api_v1_router.include_router(forms_router, prefix="/forms", tags=["forms"])
api_v1_router.include_router(participants_router, prefix="/participants", tags=["participants"])
api_v1_router.include_router(records_router, prefix="/records", tags=["records"])
api_v1_router.include_router(files_router, prefix="/files", tags=["files"])
api_v1_router.include_router(storage_router, prefix="/storage", tags=["storage"])
api_v1_router.include_router(messages_router, prefix="/messages", tags=["messages"])
api_v1_router.include_router(review_router, prefix="/review", tags=["review"])
api_v1_router.include_router(audit_router, prefix="/audit", tags=["audit"])
