import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from app.core.config import settings

async def alter_db():
    password = settings.DB_PASSWORD.get_secret_value()
    url = f"postgresql+asyncpg://{settings.DB_USER}:{password}@{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    engine = create_async_engine(url)
    
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN file_path VARCHAR(1024);"))
            print("Added file_path")
        except Exception as e:
            print(f"file_path error: {e}")
            
        try:
            await conn.execute(text("ALTER TABLE documents ADD COLUMN error_msg VARCHAR(1024);"))
            print("Added error_msg")
        except Exception as e:
            print(f"error_msg error: {e}")
            
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(alter_db())
