from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .core.database import engine
from .api.routes import router as metrics_router

app = FastAPI()

# CORS Configuration - Allow only specific domain
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://187.124.91.100",
        "https://187.124.91.100",
    ],
    allow_credentials=True,
    allow_methods=["GET", "OPTIONS"],
    allow_headers=["*"],
    max_age=3600,  # Cache CORS preflight for 1 hour
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

