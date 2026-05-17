"""DSEC AI Case Review System — FastAPI application entry point."""
import structlog
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import engine, Base
from app.core.middleware import RequestIDMiddleware
from app.api.v1 import api_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown events."""
    log.info("dsec_startup", env=settings.APP_ENV, version=settings.APP_VERSION)
    # Ensure S3 bucket exists (dev only)
    if settings.APP_ENV == "development":
        try:
            import boto3
            s3 = boto3.client(
                "s3",
                endpoint_url=settings.S3_ENDPOINT_URL,
                aws_access_key_id=settings.S3_ACCESS_KEY,
                aws_secret_access_key=settings.S3_SECRET_KEY,
            )
            s3.create_bucket(Bucket=settings.S3_BUCKET)
        except Exception:
            pass  # Bucket may already exist

    yield
    log.info("dsec_shutdown")
    await engine.dispose()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI-assisted case review platform for DJI security integrators.",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ── Middleware ────────────────────────────────────────────────────────────────

app.add_middleware(RequestIDMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Exception Handlers ────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    log.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "request_id": getattr(request.state, "request_id", None),
        },
    )

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(api_router)


# ── Health Check ──────────────────────────────────────────────────────────────

@app.get("/health", tags=["health"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}


@app.get("/", tags=["health"])
async def root():
    return {"name": settings.APP_NAME, "version": settings.APP_VERSION}
