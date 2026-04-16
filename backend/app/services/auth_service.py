"""
Serviços de autenticação e bootstrap de usuários.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.user_scope import (
    USERNAME_ADMIN,
    USER_SECTOR_SCOPE,
    USER_SECTOR_SQUADS,
    resolve_user_sector,
    resolve_user_squad_scope,
)
from app.models.user import User
from app.schemas.auth_schema import TokenPayload

logger = logging.getLogger(__name__)


class AuthService:
    """Serviço para login, JWT e seed de usuários iniciais."""

    USERNAME_ADMIN = USERNAME_ADMIN
    USER_SECTOR_SCOPE = USER_SECTOR_SCOPE
    USER_SECTOR_SQUADS = USER_SECTOR_SQUADS
    SEEDED_USERS: dict[str, tuple[str, str]] = {
        "native": ("Native2026", "user"),
        "youtube": ("YouTube2026", "user"),
        "facebook": ("Facebook2026", "user"),
    }

    @classmethod
    def resolve_user_sector(cls, username: str | None) -> str | None:
        return resolve_user_sector(username)

    @classmethod
    def resolve_user_squad_scope(cls, username: str | None) -> tuple[str, ...] | None:
        return resolve_user_squad_scope(username)

    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))

    @classmethod
    def ensure_initial_users(cls, db: Session) -> None:
        """Cria/atualiza usuários iniciais com senhas previsíveis via UPSERT."""
        seed_users = [
            (cls.USERNAME_ADMIN, settings.ADMIN_PASSWORD, "admin", False),
            *( (username, password, role, True) for username, (password, role) in cls.SEEDED_USERS.items() ),
        ]

        payload = [
            {
                "username": username,
                "password": cls.hash_password(plain_password),
                "role": role,
            }
            for username, plain_password, role, _ in seed_users
        ]

        stmt = pg_insert(User).values(payload)
        stmt = stmt.on_conflict_do_update(
            index_elements=[User.username],
            set_={
                "password": stmt.excluded.password,
                "role": stmt.excluded.role,
                "updated_at": func.now(),
            },
        )

        db.execute(stmt)
        db.commit()

        for username, plain_password, _, generated in seed_users:
            if generated:
                logger.warning("[auth-seed] senha definida para %s: %s", username, plain_password)

        logger.info("[auth-seed] seed inicial aplicado para %s usuario(s)", len(payload))

    @staticmethod
    def authenticate_user(db: Session, username: str, password: str) -> User | None:
        user = (
            db.query(User)
            .filter(func.lower(User.username) == username.strip().lower())
            .first()
        )
        if not user:
            return None

        if not AuthService.verify_password(password, user.password):
            return None

        return user

    @staticmethod
    def create_access_token(user: User) -> tuple[str, int]:
        expires_delta = timedelta(hours=settings.JWT_EXPIRATION_HOURS)
        expires_at = datetime.now(timezone.utc) + expires_delta
        sector = AuthService.resolve_user_sector(user.username)
        payload = {
            "id": user.id,
            "username": user.username,
            "role": user.role,
            "sector": sector,
            "exp": expires_at,
            "iat": datetime.now(timezone.utc),
        }
        token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
        return token, int(expires_delta.total_seconds())

    @staticmethod
    def verify_token(token: str) -> TokenPayload | None:
        try:
            decoded = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM],
            )
            return TokenPayload(**decoded)
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError, TypeError, ValueError):
            return None
