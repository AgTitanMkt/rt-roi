from fastapi import FastAPI
from sqlalchemy import text
from .core.database import engine
from .api.routes import router as metrics_router

app = FastAPI()
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

