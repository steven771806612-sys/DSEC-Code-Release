"""API v1 router — aggregates all sub-routers."""
from fastapi import APIRouter
from app.api.v1 import auth, cases, reviews, rag, ops, notifications

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(cases.router)
api_router.include_router(reviews.router)
api_router.include_router(rag.router)
api_router.include_router(ops.router)
api_router.include_router(notifications.router)
