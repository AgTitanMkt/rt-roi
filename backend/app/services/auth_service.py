"""
Serviço de autenticação JWT
"""
from datetime import datetime, timedelta
from typing import Optional
import jwt
from app.core.config import settings
class AuthService:
    """Serviço para gerenciar autenticação JWT"""
    @staticmethod
    def verify_credentials(username: str, password: str) -> bool:
        """
        Verifica credenciais do usuário admin
        Args:
            username: Nome de usuário
            password: Senha
        Returns:
            True se credenciais são válidas
        """
        return (
            username == settings.ADMIN_USERNAME and
            password == settings.ADMIN_PASSWORD
        )
    @staticmethod
    def create_access_token(username: str) -> tuple[str, int]:
        """
        Cria um token JWT
        Args:
            username: Nome do usuário
        Returns:
            Tupla (token, expires_in_seconds)
        """
        # Payload do token
        payload = {
            "username": username,
            "role": "admin",
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(hours=settings.JWT_EXPIRATION_HOURS),
        }
        # Gera o token
        token = jwt.encode(
            payload,
            settings.JWT_SECRET_KEY,
            algorithm=settings.JWT_ALGORITHM
        )
        # Calcula tempo de expiração em segundos
        expires_in = settings.JWT_EXPIRATION_HOURS * 3600
        return token, expires_in
    @staticmethod
    def verify_token(token: str) -> Optional[dict]:
        """
        Valida um token JWT e retorna seu payload
        Args:
            token: Token JWT a validar
        Returns:
            Payload do token ou None se inválido
        """
        try:
            payload = jwt.decode(
                token,
                settings.JWT_SECRET_KEY,
                algorithms=[settings.JWT_ALGORITHM]
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
