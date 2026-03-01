import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Default URL can be overridden with environment variable to avoid hardcoding secrets
DEFAULT_DATABASE_URL = (
    "mysql+mysqlconnector://user:password@localhost:3306/rpg_game"
)
DATABASE_URL = os.getenv("RPG_DATABASE_URL", DEFAULT_DATABASE_URL)


def _is_mysql_url(database_url: str) -> bool:
    normalized = str(database_url or "").lower()
    return normalized.startswith("mysql://") or normalized.startswith("mysql+") or normalized.startswith("mariadb+")


def _read_int_env(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name, "").strip()
    try:
        value = int(raw) if raw else int(default)
    except Exception:
        value = int(default)
    return max(minimum, value)


def _build_engine_kwargs(database_url: str) -> dict[str, object]:
    kwargs: dict[str, object] = {"echo": False, "future": True}
    if not _is_mysql_url(database_url):
        return kwargs

    kwargs.update(
        {
            "pool_pre_ping": True,
            "pool_recycle": _read_int_env("RPG_DB_POOL_RECYCLE_SECONDS", 1800, minimum=0),
            "pool_size": _read_int_env("RPG_DB_POOL_SIZE", 5, minimum=1),
            "max_overflow": _read_int_env("RPG_DB_MAX_OVERFLOW", 10, minimum=0),
            "pool_timeout": _read_int_env("RPG_DB_POOL_TIMEOUT_SECONDS", 30, minimum=1),
        }
    )
    return kwargs


engine = create_engine(DATABASE_URL, **_build_engine_kwargs(DATABASE_URL))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
