from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

if not settings.DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment variables.")

# echo is gated on DEBUG so production does not log every statement
# (including embedding vectors and bound parameters) to stdout.
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)

SessionLocal = async_sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with SessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()