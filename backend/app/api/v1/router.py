"""
Aggregate all v1 route modules into a single APIRouter.
Mounted at /api/v1 in app/main.py.
"""
from fastapi import APIRouter

from app.api.v1 import auth, contact, datasets, findings, studies, validation

v1_router = APIRouter(prefix="/api/v1")

v1_router.include_router(auth.router)
v1_router.include_router(studies.router)
v1_router.include_router(datasets.router)
v1_router.include_router(validation.router)
v1_router.include_router(findings.router)
v1_router.include_router(contact.router)
