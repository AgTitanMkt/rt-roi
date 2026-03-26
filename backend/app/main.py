from fastapi import FastAPI
from sqlalchemy import text
from .core.database import engine
from .api.routes import router as metrics_router

app = FastAPI(
    cors_allowed_origins="http://187.124.91.100/",
    cors_allowed_headers=[],
    cors_allowd_methods=["GET", "OPTIONS"],
)
app.include_router(metrics_router)

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
    except:
        return {"db": "error"}

