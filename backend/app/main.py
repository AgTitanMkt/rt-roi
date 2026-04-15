from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from .core.database import engine
from .api.routes import router

app = FastAPI()

# CORS Configuration - Allow frontend and local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",      # Vite dev server
        "http://localhost:3000",      # Production frontend
        "http://127.0.0.1:5173",      # Local testing
        "http://127.0.0.1:3000",      # Local testing
        "http://187.124.91.100",      # Production domain
        "https://187.124.91.100",     # Production domain (HTTPS)
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    max_age=3600,  # Cache CORS preflight for 1 hour
)

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
    except:
        return {"db": "error"}

