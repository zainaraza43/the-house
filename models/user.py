from sqlalchemy import Column, Integer, BigInteger, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True)
    discord_account_id = Column(BigInteger, unique=True, nullable=False)
