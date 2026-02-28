from pydantic_settings import BaseSettings
from pydantic import SecretStr


class Settings(BaseSettings):
    class config:
        env_file = ".env"
        extra = "ignore"

    DB_USER: str
    DB_PASSWORD: SecretStr
    DB_HOST: str
    DB_PORT: int
    DB_NAME: str


settings = Settings() # type: ignore
