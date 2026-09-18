from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
    display_name: str | None = None


class MeResponse(BaseModel):
    user_id: int
    username: str
    role: str
    display_name: str | None = None
