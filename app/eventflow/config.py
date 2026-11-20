import re

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = Field(min_length=1)
    api_users: dict[str, str] = Field(min_length=1)
    seed_on_start: bool = True
    seed_events: int = 50
    seed_capacity: int = 500
    reservation_ttl_minutes: int = 10

    @field_validator("api_users")
    @classmethod
    def validate_api_users(cls, users: dict[str, str]) -> dict[str, str]:
        if any(
            not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,63}", name)
            or not re.fullmatch(r"[0-9a-f]{64}", digest)
            for name, digest in users.items()
        ):
            raise ValueError("API_USERS must map lowercase user IDs to SHA-256 token hashes")
        if len(set(users.values())) != len(users):
            raise ValueError("API_USERS token hashes must be unique")
        return users


settings = Settings()
