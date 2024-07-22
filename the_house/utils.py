import logging

import requests

from models import User, LeagueOfLegendsAccount, Guild
from services import _Services
from config import RIOT_API_KEY

services = _Services()

BASE_URL_AMERICAS = "https://americas.api.riotgames.com"

lol_accounts = {}


def create_user(discord_account_id: int):
    db = services.db
    user = User(discord_account_id=discord_account_id)
    db.add(user)
    db.commit()
    return user


def get_user_by_discord_account_id(discord_account_id: int):
    db = services.db
    return db.query(User).filter(User.discord_account_id == discord_account_id).first()


def create_guild(guild_id: int):
    db = services.db
    guild = Guild(guild_id=guild_id)
    db.add(guild)
    db.commit()
    return guild


def get_guild_by_guild_id(guild_id: int):
    db = services.db
    return db.query(Guild).filter(Guild.guild_id == guild_id).first()


def get_account_by_riot_id(username: str, tag_line: str):
    url = f"{BASE_URL_AMERICAS}/riot/account/v1/accounts/by-riot-id/{username}/{tag_line}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_summoner_by_puuid(puuid: str, region: str):
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_match_ids_by_puuid(puuid: str, start=0, count=1):
    url = f"{BASE_URL_AMERICAS}/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_match_details(match_id):
    url = f"{BASE_URL_AMERICAS}/lol/match/v5/matches/{match_id}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_live_match_details(puuid: str, region: str):
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    logging.info(response.json())
    return response.json()


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


async def update_lol_accounts():
    db = services.db
    accounts = db.query(LeagueOfLegendsAccount).all()

    for account in accounts:
        try:
            match_ids = get_match_ids_by_puuid(account.puuid, count=1)
            last_match_id = match_ids[0]
            match_details = get_match_details(last_match_id)
            last_match_game_id = match_details['info']['gameId']

            live_match_details = get_live_match_details(account.puuid, account.region)
            live_match_game_id = live_match_details.get('gameId', None)

            logging.info(
                f"Last match for {account.puuid}: {last_match_game_id} | Live match: {live_match_game_id} | "
                f"lol_accounts={lol_accounts}")

            if lol_accounts.get(account.puuid, None) is not None:
                if not live_match_game_id:
                    # game just ended
                    if lol_accounts.get(account.puuid).get('live_match', None) == last_match_game_id:
                        logging.info(
                            f"Game just ended for {account.puuid} ({lol_accounts[account.puuid]} == {last_match_game_id})")
                else:
                    if lol_accounts.get(account.puuid).get('live_match', None) != live_match_game_id:
                        logging.info(
                            f"Game started for {account.puuid} ({lol_accounts[account.puuid]} != {live_match_game_id})")

            lol_accounts[account.puuid] = {
                'last_match': last_match_game_id,
                'live_match': live_match_game_id
            }

        except KeyError as ke:
            logging.error(f"KeyError processing account {account.puuid}: {ke}")
        except Exception as e:
            logging.error(f"Error processing account {account.puuid}: {e}")
