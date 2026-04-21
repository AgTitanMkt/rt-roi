import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .core.database import SessionLocal, engine
from .api.routes import router
from .services.auth_service import AuthService

logger = logging.getLogger(__name__)


from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_PAYLOAD_SIZE = 2 * 1024 * 1024  # 2MB

app = FastAPI()

# CORS Configuration - Restrict to localhost/internal dev only
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://187.124.91.100",
        "https://187.124.91.100",
        "https://roi.agenciatitandev.com",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,
)

# Middleware to limit payload size
@app.middleware("http")
async def limit_payload_size(request: Request, call_next):
    if request.method in ("POST", "PUT", "PATCH"):
        body = await request.body()
        if len(body) > MAX_PAYLOAD_SIZE:
            return JSONResponse(
                status_code=413,
                content={"detail": f"Payload too large. Limit is {MAX_PAYLOAD_SIZE // (1024 * 1024)}MB."}
            )
    return await call_next(request)


@app.on_event("startup")
def bootstrap_auth_users() -> None:
    db = SessionLocal()
    try:
        AuthService.ensure_initial_users(db)
    except SQLAlchemyError as exc:
        logger.warning("bootstrap de usuarios ignorado (migracao pendente): %s", exc)
    finally:
        db.close()


app.include_router(router)


@app.get("/")
def get_root():
    return {"Hello": "World"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"db": "ok"}
    except Exception:
        return {"db": "error"}
