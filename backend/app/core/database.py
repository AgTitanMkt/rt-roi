import os
from pathlib import Path
from typing import cast
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
FORCE_DATABASE_URL = str(os.getenv("FORCE_DATABASE_URL", "")).strip().lower() in {"1", "true", "yes", "on"}

# Outside Docker, service DNS names like 'postgres' are not resolvable.
# Allow a local DSN fallback without changing container behavior.
# Set FORCE_DATABASE_URL=true to keep DATABASE_URL even outside Docker.
if not FORCE_DATABASE_URL and not Path("/.dockerenv").exists() and "@postgres:" in (DATABASE_URL or ""):
	DATABASE_URL = os.getenv("DATABASE_URL_LOCAL", DATABASE_URL)

if not DATABASE_URL:
	raise RuntimeError("DATABASE_URL nao configurada")

engine = create_engine(cast(str, DATABASE_URL))
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()