import asyncio
import logging
import threading

import discord
import requests
from discord import app_commands

from config import RIOT_API_KEY
from models import User, LeagueOfLegendsAccount, Guild
from services import services

bot = services.bot

BASE_URL_AMERICAS = "https://americas.api.riotgames.com"
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

lol_accounts = {}
bets = {}


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

            if lol_accounts.get(account.puuid, None) is not None:
                if not live_match_game_id:
                    # game just ended
                    if lol_accounts.get(account.puuid).get('live_match', None) == last_match_game_id:
                        logging.info(
                            f"Game just ended for {account.puuid} ({lol_accounts[account.puuid]} == {last_match_game_id})")
                        await send_match_start_discord_message(account.guild.guild_id, account.guild.channel_id,
                                                   f"Game just ended for <@{account.user.discord_account_id}>")
                else:
                    if lol_accounts.get(account.puuid).get('live_match', None) != live_match_game_id:
                        new_game_bet = {
                            "game_id": live_match_game_id,
                            "match_id": None,
                            "win_odds": 1.5,
                        }
                        await send_match_start_discord_message(account.guild.guild_id, account.guild.channel_id,
                                                   f"Game just started for <@{account.user.discord_account_id}>")

            lol_accounts[account.puuid] = {
                'last_match': last_match_game_id,
                'live_match': live_match_game_id
            }

        except KeyError as ke:
            logging.error(f"KeyError processing account {account.puuid}: {ke}")
        except Exception as e:
            logging.error(f"Error processing account {account.puuid}: {e}")


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print(e)
    print(f'Bot is ready. Logged in as {bot.user}')

    await asyncio.create_task(update_accounts())


@bot.tree.command(name="set-betting-channel", description="Set the betting channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_betting_channel(interaction: discord.Interaction):
    guild = get_guild_by_guild_id(interaction.guild.id)
    if not guild:
        guild = create_guild(interaction.guild.id)

    guild.channel_id = interaction.channel.id
    await interaction.response.send_message(f'Betting channel has been set to {interaction.channel.mention}.')


@bot.tree.command(name="set-league-of-legends-account", description="Add a League of Legends account")
@app_commands.describe(riot_id="The Riot ID in the format `USERNAME#TAGLINE`", region="The region of the account")
@app_commands.choices(region=[
    app_commands.Choice(name="NA", value="na1"),
    app_commands.Choice(name="EUW", value="euw1"),
    app_commands.Choice(name="KR", value="kr"),
    app_commands.Choice(name="JP", value="jp1"),
    app_commands.Choice(name="EUNE", value="eun1"),
    app_commands.Choice(name="BR", value="br1"),
    app_commands.Choice(name="OCE", value="oc1"),
    app_commands.Choice(name="LAN", value="la1"),
    app_commands.Choice(name="LAS", value="la2"),
    app_commands.Choice(name="TR", value="tr1"),
    app_commands.Choice(name="RU", value="ru"),
    app_commands.Choice(name="ME", value="me1"),
    app_commands.Choice(name="PH", value="ph2"),
    app_commands.Choice(name="SG", value="sg2"),
    app_commands.Choice(name="TH", value="th2"),
    app_commands.Choice(name="TW", value="tw2"),
    app_commands.Choice(name="VN", value="vn2"),
])
async def set_league_of_legends_account(interaction: discord.Interaction, region: app_commands.Choice[str],
                                        riot_id: str):
    if "#" not in riot_id:
        await interaction.response.send_message("Invalid format. The Riot ID must be in the format `USERNAME#TAGLINE`.")
        return

    username, tag_line = riot_id.split("#", 1)

    try:
        # Step 1: Get account by Riot ID
        account_info = get_account_by_riot_id(username, tag_line)
        if 'status' in account_info and account_info['status']['status_code'] != 200:
            await interaction.response.send_message(f"Error: {account_info['status']['message']}")
            return

        puuid = account_info.get('puuid')
        if not puuid:
            await interaction.response.send_message("Could not retrieve PUUID from the provided Riot ID.")
            return

        # Step 2: Get summoner by PUUID
        summoner_info = get_summoner_by_puuid(puuid, region.value)
        if 'status' in summoner_info and summoner_info['status']['status_code'] != 200:
            await interaction.response.send_message(f"Error: {summoner_info['status']['message']}")
            return

        # Step 3: Set League of Legends account in the database

        user = get_user_by_discord_account_id(interaction.user.id)
        if not user:
            user = create_user(interaction.user.id)

        guild = get_guild_by_guild_id(interaction.guild.id)
        if not guild:
            guild = create_guild(interaction.guild.id)

        set_lol_account(user.id, guild.id, region.value, puuid)

        # Step 4: Send success message
        await interaction.response.send_message(f'Riot ID: "{riot_id}" on {region.name} has been set.')

    except Exception as e:
        logging.error(f"Error processing League of Legends account: {e}")
        await interaction.response.send_message(
            "An error occurred while setting the League of Legends account. Please try again later.")


async def send_match_start_discord_message(guild_id, channel_id, message, timeout=3):
    try:
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild:
            channel = bot.get_channel(channel_id)
            if channel:
                await asyncio.wait_for(channel.send(message), timeout=timeout)
    except asyncio.TimeoutError:
        logging.error(f"Sending message timed out after {timeout} seconds")


def calculate_win_odds():
    pass


async def update_accounts():
    while True:
        await update_lol_accounts()
        await asyncio.sleep(5)