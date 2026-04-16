from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenPayload(BaseModel):
    id: int
    username: str
    role: str
    sector: str | None = None
    exp: int


class CurrentUserResponse(BaseModel):
    id: int
    username: str
    role: str
    sector: str | None = None

