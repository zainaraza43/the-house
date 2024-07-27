from functools import cached_property

import discord
from discord.ext import commands
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

    @cached_property
    def bot(self) -> discord.Client:
        intents = discord.Intents.default()
        intents.message_content = True
        bot = commands.Bot(command_prefix='!', intents=intents)

        return bot


services = _Services()
