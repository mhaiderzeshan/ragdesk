from app.schemas import RegistrationRequest, OrganizationCreate, UserCreate
from app.repositories.auth import AuthRepository
from app.core.security import get_password_hash


class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo

    async def register_new_org(self, payload: RegistrationRequest):
        # Hash the password here (Service handles business logic)
        hashed_password = get_password_hash(payload.password)

        # Prepare the schemas for the Repository
        org_data = OrganizationCreate(name=payload.org_name)
        user_data = UserCreate(email=payload.email, password=hashed_password)

        return await self.repo.create_org_and_user(
            org_in=org_data,
            user_in=user_data,
            hashed_password=hashed_password
        )
