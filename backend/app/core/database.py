import os
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

# Outside Docker, service DNS names like 'postgres' are not resolvable.
# Allow a local DSN fallback without changing container behavior.
if not Path("/.dockerenv").exists() and "@postgres:" in (DATABASE_URL or ""):
	DATABASE_URL = os.getenv("DATABASE_URL_LOCAL", DATABASE_URL)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()