import os

import requests

from models import User
from services import _Services

services = _Services()
RIOT_API_KEY = os.getenv('RIOT_API_KEY')

BASE_URL_AMERICAS = "https://americas.api.riotgames.com"
BASE_URL_NA1 = "https://na1.api.riotgames.com"


def create_user(discord_account_id: int):
    db = services.db
    user = User(discord_account_id=discord_account_id)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_discord_account_id(discord_account_id: int):
    db = services.db
    return db.query(User).filter(User.discord_account_id == discord_account_id).first()


def get_account_by_riot_id(riot_id, tag_line):
    url = f"{BASE_URL_AMERICAS}/riot/account/v1/accounts/by-riot-id/{riot_id}/{tag_line}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_summoner_by_puuid(puuid):
    url = f"{BASE_URL_NA1}/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_match_ids_by_puuid(puuid, start=0, count=1):
    url = f"{BASE_URL_AMERICAS}/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()


def get_match_details(match_id):
    url = f"{BASE_URL_AMERICAS}/lol/match/v5/matches/{match_id}?api_key={RIOT_API_KEY}"
    response = requests.get(url)
    return response.json()
