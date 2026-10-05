import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.logging import logger
from app.core.security import hash_password
from app.db.base import Base
from app.db.models.user import User
from app.db.session import AsyncSessionLocal, async_engine


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id

        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Ensure tables exist
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed initial Admin user if not exists
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        stmt = select(User).where(User.email == settings.admin_email.lower().strip())
        res = await session.execute(stmt)
        admin = res.scalars().first()
        if not admin:
            admin_user = User(
                email=settings.admin_email.lower().strip(),
                hashed_password=hash_password(settings.admin_password),
                full_name="Platform Administrator",
                is_active=True,
                is_superuser=True,
            )
            session.add(admin_user)
            await session.commit()
            logger.info(f"Initialized default administrator account: {settings.admin_email}")

    yield

    # Shutdown
    await async_engine.dispose()


app = FastAPI(
    title="Lead Intelligence & Generation Platform API",
    description=(
        "Production-grade backend REST API for business discovery, public web enrichment, "
        "Apollo contact intelligence, Jev AI qualification, deterministic scoring, and Google Sheets synchronization.\n\n"
        "Built exclusively as a backend service for existing and custom admin dashboards."
    ),
    version="1.0.0",
    docs_url="/docs" if settings.enable_api_docs else None,
    redoc_url="/redoc" if settings.enable_api_docs else None,
    openapi_url="/openapi.json" if settings.enable_api_docs else None,
    lifespan=lifespan,
)

# Request ID & Security Headers
app.add_middleware(RequestContextMiddleware)

# CORS Middleware (Enabled if enable_frontend_api is True)
if settings.enable_frontend_api and settings.cors_origin_list:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )


# Consistent Error Handling
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request_id,
                "details": exc.details,
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    from fastapi.encoders import jsonable_encoder
    request_id = getattr(request.state, "request_id", None)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters or payload.",
                "request_id": request_id,
                "details": {"errors": jsonable_encoder(exc.errors())},
            }
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"Unhandled error processing request: {str(exc)}", exc_info=True, extra={"request_id": request_id})
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred. Please contact system support.",
                "request_id": request_id,
            }
        },
    )


# Mount routers
app.include_router(api_router)
