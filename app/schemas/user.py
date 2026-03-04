from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)

    class Config:
        orm_mode = True

        schema_extra = {
            "example": {
                "email": "user@example.com",
                "hashed_password": "hashedpassword123",
            }
        }
