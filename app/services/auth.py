from app.schemas import RegistrationRequest, OrganizationCreate, UserCreate
from app.repositories.auth import AuthRepository
from app.core.security import get_password_hash, verify_password, create_access_token
from app.models import User


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

    async def authenticate_user(self, email: str, password: str):
        user = await self.repo.get_user_by_email(email)
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_user_token(self, user: User) -> str:
        # Create the JWT token with the user data
        token_data = {
            "sub": str(user.id),
            "org_id": str(user.org_id),
            "email": user.email,
            "role": user.role,
        }
        return create_access_token(data=token_data)
