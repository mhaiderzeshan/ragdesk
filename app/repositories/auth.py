from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User, Organization
from app.schemas import OrganizationCreate, UserCreate
from app.core.security import get_password_hash


class AuthRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_org_and_user(
        self,
        org_in: OrganizationCreate,
        user_in: UserCreate,
        hashed_password: str
    ) -> User:
        async with self.session.begin():
            # Clean unpacking
            new_org = Organization(**org_in.model_dump())
            self.session.add(new_org)
            await self.session.flush()

            # Using 'exclude' to handle the password logic gracefully
            user_data = user_in.model_dump(exclude={"password"})
            new_user = User(
                **user_data,
                hashed_password=hashed_password,
                org_id=new_org.id
            )
            self.session.add(new_user)
            # Final flush to ensure IDs are populated for the return
            await self.session.flush()
            return new_user
