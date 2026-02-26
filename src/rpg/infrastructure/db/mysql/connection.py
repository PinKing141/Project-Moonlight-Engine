import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Default URL can be overridden with environment variable to avoid hardcoding secrets
DEFAULT_DATABASE_URL = (
    "mysql+mysqlconnector://user:password@localhost:3306/rpg_game"
)
DATABASE_URL = os.getenv("RPG_DATABASE_URL", DEFAULT_DATABASE_URL)

engine = create_engine(DATABASE_URL, echo=False, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
