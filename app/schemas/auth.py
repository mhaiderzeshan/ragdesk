from pydantic import BaseModel, EmailStr, ConfigDict
import uuid


class UserResponse(BaseModel):
    """
    This is what we send BACK to the client. 
    Notice: No password or password_hash here!
    """
    id: uuid.UUID
    email: EmailStr
    org_id: uuid.UUID
    role: str

    model_config = ConfigDict(from_attributes=True)


class RegistrationRequest(BaseModel):
    """
    This is what we expect FROM the client when they want to register.
    """
    org_name: str
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: uuid.UUID | None = None
    org_id: uuid.UUID | None = None


class UserContext(BaseModel):
    user_id: uuid.UUID
    org_id: uuid.UUID
    email: EmailStr
    role: str = "user"
