from functools import cached_property

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session, scoped_session

from config import DATABASE_URL
from models import Base

engine = create_engine(DATABASE_URL, echo=True)
Base.metadata.create_all(engine)
SessionLocal = scoped_session(sessionmaker(autocommit=False, autoflush=False, bind=engine))


class _Services:
    @cached_property
    def db(self) -> Session:
        return SessionLocal()
