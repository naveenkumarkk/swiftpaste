import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.db.database import create_db_and_tables  # ,AsyncSessionLocal
from app.core.auth.manager import fastapi_users
from app.core.auth.backend import auth_backend
from app.core.auth.oauth.google import google_oauth_router
from app.schemas.user import UserRead, UserCreate, UserUpdate
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.core.exception_handlers import (
    app_error_handler,
    validation_error_handler,
    http_error_handler,
    unhandled_error_handler,
)
from app.core.errors import AppError
from app.core.middleware.request_logging import RequestLoggingMiddleware
from app.core.logging import setup_logging
from app.api.v1.routes import snippet, health

setup_logging("DEBUG" if settings.DEBUG else "INFO")
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting Application")
    await create_db_and_tables()
    # await with AsyncSessionLocal() as session:
    #     await seed_initial_data(session)
    print("Application Started Successfully")
    yield
    print("Shutting Down Application")


app = FastAPI(
    title="SwiftPaste",
    description="SwiftPaste is a scalable code-snippet manager (Pastebin-style).",
    version="1.0.0",
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc UI
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# Logging Middleware
app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)
app.add_exception_handler(Exception, unhandled_error_handler)


app.include_router(
    fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"]
)
app.include_router(google_oauth_router, prefix="/auth/google", tags=["auth"])
app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"],
)
app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)
app.include_router(
    snippet.router,
    prefix=f"{settings.V1_API_PREFIX}/snippet",
    tags=["Snippets"],
)

app.include_router(
    health.router,
    prefix=f"{settings.V1_API_PREFIX}/health",
    tags=["Health"],
)


@app.get("/")
async def root():
    return {"message": "Hello from Swift paste"}
