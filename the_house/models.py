from sqlalchemy import Column, Integer, BigInteger, ForeignKey, String, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    discord_account_id = Column(BigInteger, unique=True, nullable=False)

    lol_accounts = relationship('LeagueOfLegendsAccount', back_populates='user')
    banks = relationship('Bank', back_populates='user')


class Guild(Base):
    __tablename__ = 'guilds'
    id = Column(Integer, primary_key=True)
    guild_id = Column(BigInteger, unique=True, nullable=False)
    channel_id = Column(BigInteger, nullable=True)
    currency = Column(String, default='coins')

    lol_accounts = relationship('LeagueOfLegendsAccount', back_populates='guild')
    banks = relationship('Bank', back_populates='guild')


class Bank(Base):
    __tablename__ = 'banks'
    id = Column(Integer, primary_key=True)
    coins = Column(Integer, default=50)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    guild_id = Column(Integer, ForeignKey('guilds.id'), nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'guild_id', name='_user_guild_bank_uc'),)

    user = relationship('User', back_populates='banks')
    guild = relationship('Guild', back_populates='banks')


class LeagueOfLegendsAccount(Base):
    __tablename__ = 'league_of_legends_accounts'
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey('users.id'), nullable=False)
    guild_id = Column(BigInteger, ForeignKey('guilds.id'), nullable=False)
    region = Column(String, nullable=False)
    puuid = Column(String, nullable=False)

    __table_args__ = (UniqueConstraint('user_id', 'guild_id', name='_user_guild_lol_uc'),)

    user = relationship('User', back_populates='lol_accounts')
    guild = relationship('Guild', back_populates='lol_accounts')
