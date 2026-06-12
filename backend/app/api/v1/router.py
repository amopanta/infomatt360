from fastapi import APIRouter

from app.api.v1.assignments import router as assignments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.forms import router as forms_router
from app.api.v1.health import router as health_router
from app.api.v1.identity import router as identity_router
from app.api.v1.participants import router as participants_router
from app.api.v1.project_context import router as project_context_router
from app.api.v1.security import router as security_router

api_v1_router = APIRouter()

api_v1_router.include_router(health_router, prefix="/health", tags=["health"])
api_v1_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_v1_router.include_router(security_router, prefix="/security", tags=["security"])
api_v1_router.include_router(identity_router, prefix="/identity", tags=["identity"])
api_v1_router.include_router(assignments_router, prefix="/assignments", tags=["assignments"])
api_v1_router.include_router(project_context_router, prefix="/projects", tags=["project-context"])
api_v1_router.include_router(forms_router, prefix="/forms", tags=["forms"])
api_v1_router.include_router(participants_router, prefix="/participants", tags=["participants"])
