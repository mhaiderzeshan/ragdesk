from pydantic import BaseModel, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)

    class Config:
        orm_mode = True

        schema_extra = {
            "example": {
                "name": "Organization Name",
            }
        }
