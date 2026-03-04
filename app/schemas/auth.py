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

    model_config = ConfigDict(from_attributes=True)


class RegistrationRequest(BaseModel):
    """
    This is what we expect FROM the client when they want to register.
    """
    org_name: str
    email: EmailStr
    password: str
