from models import User, LeagueOfLegendsAccount, Guild, Bank
from services import services, logging


def create_user(discord_account_id: int):
    db = services.db
    user = User(discord_account_id=discord_account_id)
    db.add(user)
    db.commit()
    return user


def get_user_by_user_table_id(user_id: int):
    db = services.db
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_discord_account_id(discord_account_id: int):
    db = services.db
    return db.query(User).filter(User.discord_account_id == discord_account_id).first()


def create_guild(guild_id: int):
    db = services.db
    guild = Guild(guild_id=guild_id)
    db.add(guild)
    db.commit()
    return guild


def create_bank(user_id: int, guild_id: int):
    db = services.db
    bank = Bank(user_id=user_id, guild_id=guild_id)
    db.add(bank)
    db.commit()
    return bank


def get_bank_by_user_and_guild(user_id: int, guild_id: int):
    db = services.db
    return db.query(Bank).filter_by(user_id=user_id, guild_id=guild_id).first()


def get_guild_by_guild_id(guild_id: int):
    db = services.db
    return db.query(Guild).filter(Guild.guild_id == guild_id).first()


def set_lol_account(user_id: int, guild_id: int, region: str, puuid: str):
    db = services.db
    existing_account = db.query(LeagueOfLegendsAccount).filter_by(
        user_id=user_id,
        guild_id=guild_id
    ).first()

    if existing_account:
        existing_account.region = region
        existing_account.puuid = puuid
        db.commit()
    else:
        new_account = LeagueOfLegendsAccount(
            user_id=user_id,
            guild_id=guild_id,
            region=region,
            puuid=puuid
        )
        db.add(new_account)
        db.commit()


def get_lol_account(user_id: int, guild_id: int):
    db = services.db
    account = db.query(LeagueOfLegendsAccount).filter_by(
        user_id=user_id,
        guild_id=guild_id
    ).first()

    return account


def get_lol_accounts_by_puuid(puuid: str):
    db = services.db
    accounts = db.query(LeagueOfLegendsAccount).filter_by(puuid=puuid).all()
    return accounts


def get_all_unique_puuids():
    db = services.db
    puuids = db.query(LeagueOfLegendsAccount.puuid).distinct().all()
    return {result[0] for result in puuids}


def get_lol_accounts_by_guild_id(guild_id: int) -> list[LeagueOfLegendsAccount]:
    db = services.db
    return db.query(LeagueOfLegendsAccount).filter_by(guild_id=guild_id).all()


def get_all_league_of_legends_accounts() -> list[LeagueOfLegendsAccount]:
    db = services.db
    return db.query(LeagueOfLegendsAccount).all()


def set_bank_coins(user_id: int, guild_id: int, coins: int):
    db = services.db
    bank = db.query(Bank).filter_by(user_id=user_id, guild_id=guild_id).first()
    if bank:
        bank.coins = coins
        db.commit()
    else:
        logging.error(f"Bank not found for user_id {user_id} and guild_id {guild_id}")


def increment_multiple_bank_coins(banks: list[Bank], coins: float):
    db = services.db
    for bank in banks:
        bank.coins += coins
    db.commit()


def get_banks_sorted_by_coins_for_guild(guild_id: int) -> list:
    db = services.db
    sorted_banks = (
        db.query(Bank)
        .filter(Bank.guild_id == guild_id)
        .order_by(Bank.coins.desc())
        .all()
    )
    return sorted_banks


def get_all_banks() -> list[Bank]:
    db = services.db
    return db.query(Bank).all()
