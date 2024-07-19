from sqlalchemy import Column, Integer, BigInteger, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()


class Guild(Base):
    __tablename__ = 'guilds'

    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, unique=True, nullable=False)
