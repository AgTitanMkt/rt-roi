"""
Middleware de autenticação JWT
"""
from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import AuthService

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = security) -> dict:
    """
    Dependency para validar token JWT
    Args:
        credentials: Credenciais HTTP Bearer
    Returns:
        Payload do token validado
    Raises:
        HTTPException: Se token inválido ou expirado
    """
    token = credentials.credentials
    payload = AuthService.verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido ou expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
