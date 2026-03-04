from fastapi import FastAPI

from app.api.endpoints import auth
from app.db import Base, engine

app = FastAPI()


@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

app.include_router(auth.router)


@app.get("/")
async def index():
    return {"message": "Welcome"}
