from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine():
    return create_engine(
        get_settings().database_url, pool_pre_ping=True, pool_timeout=3,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=45000"},
    )


def session_factory():
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_session():
    with session_factory()() as session:
        yield session
