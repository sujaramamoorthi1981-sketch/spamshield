import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, spam
from app.core.config import settings
from app.core.errors import AppError
from app.database.session import Base, engine
from app import models  # noqa: F401  (register tables)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("spamshield")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.jwt_secret.startswith("dev-only"):
        log.warning("Using the default JWT secret. Set JWT_SECRET in .env before deploying.")
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title="SpamShield API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error(code: str, message: str, status: int) -> JSONResponse:
    return JSONResponse(status_code=status, content={"success": False, "error": {"code": code, "message": message}})


@app.exception_handler(AppError)
async def app_error_handler(_: Request, exc: AppError):
    return _error(exc.code, exc.message, exc.status)


@app.exception_handler(RequestValidationError)
async def validation_handler(_: Request, exc: RequestValidationError):
    return _error("INVALID_INPUT", "Please check the values you entered and try again.", 422)


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _error("INTERNAL_ERROR", "Something went wrong on our side. Please try again.", 500)


@app.get("/api/health")
def health():
    return {"success": True, "data": {"status": "ok"}, "message": "OK"}


app.include_router(auth.router)
app.include_router(spam.router)
