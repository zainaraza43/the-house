import asyncio
import logging
import time

import aiohttp
import discord
from discord import app_commands
from discord.ui import View, Button

from config import RIOT_API_KEY
from models import User, LeagueOfLegendsAccount, Guild, Bank
from services import services

bot = services.bot
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(lineno)d - %(message)s'
)

CONTINENT_TO_REGION = {
    "na1": "americas",
    "br1": "americas",
    "la1": "americas",
    "la2": "americas",
    "kr": "asia",
    "jp1": "asia",
    "eun1": "europe",
    "euw1": "europe",
    "me1": "europe",
    "tr1": "europe",
    "ru": "europe",
    "oc1": "sea",
    "ph2": "sea",
    "sg2": "sea",
    "th2": "sea",
    "tw2": "sea",
    "vn2": "sea"
}

cached_league_of_legends_games = {}
active_bets = {}


def create_user(discord_account_id: int):
    db = services.db
    existing_user = db.query(User).filter_by(discord_account_id=discord_account_id).first()
    if existing_user:
        logging.info(f"User with discord_account_id {discord_account_id} already exists.")
        return existing_user

    new_user = User(discord_account_id=discord_account_id)
    db.add(new_user)
    try:
        db.commit()
        logging.info(f"Created new user with discord_account_id {discord_account_id}.")
    except Exception as e:
        db.rollback()
        logging.error(f"Error creating user: {e}")
        raise
    return new_user


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


def set_bank_coins(user_id: int, guild_id: int, coins: int):
    db = services.db
    bank = db.query(Bank).filter_by(user_id=user_id, guild_id=guild_id).first()
    if bank:
        bank.coins = coins
        db.commit()
    else:
        logging.error(f"Bank not found for user_id {user_id} and guild_id {guild_id}")


async def fetch_json(url):
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                logging.error(f"Failed to fetch data: {response.status}, {await response.text()}")
                raise Exception(f"Failed to fetch data: {response.status}, {await response.text()}")
            return await response.json()


async def get_account_by_riot_id(username: str, tag_line: str, region: str) -> dict:
    continent = CONTINENT_TO_REGION.get(region)
    url = f"https://{continent}.api.riotgames.com/riot/account/v1/accounts/by-riot-id/{username}/{tag_line}?api_key={RIOT_API_KEY}"
    return await fetch_json(url)


async def get_account_info_by_puuid(puuid: str, region: str) -> dict:
    continent = CONTINENT_TO_REGION.get(region)
    url = f"https://{continent}.api.riotgames.com/riot/account/v1/accounts/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    return await fetch_json(url)


async def get_summoner_by_puuid(puuid: str, region: str) -> dict:
    url = f"https://{region}.api.riotgames.com/lol/summoner/v4/summoners/by-puuid/{puuid}?api_key={RIOT_API_KEY}"
    return await fetch_json(url)


async def get_match_ids_by_puuid(puuid: str, region: str, count: int, start=0, queue_id=None) -> list:
    continent = CONTINENT_TO_REGION.get(region)
    if queue_id is not None:
        url = f"https://{continent}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?queue={queue_id}&start={start}&count={count}&api_key={RIOT_API_KEY}"
    else:
        url = f"https://{continent}.api.riotgames.com/lol/match/v5/matches/by-puuid/{puuid}/ids?start={start}&count={count}&api_key={RIOT_API_KEY}"
    return await fetch_json(url)


async def get_match_details(match_id: str, region: str) -> dict:
    continent = CONTINENT_TO_REGION.get(region)
    url = f"https://{continent}.api.riotgames.com/lol/match/v5/matches/{match_id}?api_key={RIOT_API_KEY}"
    return await fetch_json(url)


async def get_live_match_details(puuid: str, region: str) -> dict:
    url = f"https://{region}.api.riotgames.com/lol/spectator/v5/active-games/by-summoner/{puuid}?api_key={RIOT_API_KEY}"
    return await fetch_json(url)


async def get_champion_icon(champion_id: int, version: str = "14.14.1") -> str:
    url = f"https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/champion.json"
    data = await fetch_json(url)

    champion_data = data.get("data", {})
    for champion_name, champion_info in champion_data.items():
        if champion_info.get("key") == str(champion_id):
            image_filename = champion_info["image"]["full"]
            return f"https://ddragon.leagueoflegends.com/cdn/{version}/img/champion/{image_filename}"

    logging.error("Champion ID not found")
    raise Exception("Champion ID not found")


async def calculate_odds(puuid: str, region: str, queue_id=int) -> tuple:
    wins = 0
    match_ids = await get_match_ids_by_puuid(puuid=puuid, region=region, count=20, queue_id=queue_id)
    total_games = len(match_ids)
    for match_id in match_ids:
        match_details = await get_match_details(match_id, region)
        for participant in match_details['info']['participants']:
            if participant['puuid'] == puuid:
                if participant['win']:
                    wins += 1
                break

    win_rate = wins / total_games if total_games != 0 else 0.5
    lose_rate = 1 - win_rate
    win_odds = 1 / win_rate if win_rate != 0 else float('inf')
    lose_odds = 1 / lose_rate if lose_rate != 0 else float('inf')

    return round(win_odds, 2), round(lose_odds, 2)


async def update_league_of_legends_accounts():
    db = services.db
    accounts = db.query(LeagueOfLegendsAccount).all()

    logging.info("Current bets = " + str(active_bets))

    for account in accounts:
        try:
            await process_league_of_legends_account(account)
        except Exception as e:
            logging.error(f"Error processing League of Legends account: {e}")


async def process_league_of_legends_account(account: LeagueOfLegendsAccount):
    # Account properties
    puuid = account.puuid
    region = account.region

    # Get Previous Match ID
    match_ids = await get_match_ids_by_puuid(puuid=puuid, region=region, count=1)
    last_match_id = match_ids[0]

    # Get Previous Match Details
    previous_match_details = await get_match_details(last_match_id, region)

    # Get Live Match Details
    try:
        live_match_details = await get_live_match_details(puuid, region)
    except Exception as e:
        logging.error(f"Error getting live match details for puuid {puuid} in region {region}: {e}")
        live_match_details = {}

    # get ids of previous and live match
    live_match_game_id = live_match_details.get('gameId', None)
    previous_match_info = previous_match_details.get('info', None)
    if not previous_match_info:
        logging.error(f"Could not get previous match info for puuid {puuid}")
        raise Exception(f"Could not get previous match info for puuid {puuid}")
    previous_match_game_id = previous_match_info.get('gameId', None)

    if await league_of_legends_account_just_start_game(live_match_details, puuid):
        queue_id = previous_match_info.get('queueId', None)
        game_start_time = live_match_details.get("gameStartTime", None)
        win_odds, lose_odds = await calculate_odds(puuid, region, queue_id=queue_id)
        active_bets[puuid] = {
            'win_odds': win_odds,
            'lose_odds': lose_odds,
            'start_time': game_start_time,
            'bets': []
        }
        await send_match_start_discord_message(account, live_match_details)
        logging.info(f"Sent match start message for puuid {puuid}")

    cached_league_of_legends_games[puuid] = {
        'previous_match_game_id': previous_match_game_id,
        'live_match_game_id': live_match_game_id
    }


async def league_of_legends_account_just_start_game(live_match_details: dict, puuid: str) -> bool:
    if not live_match_details:
        return False

    cached_player_matches = cached_league_of_legends_games[puuid]

    if not cached_player_matches or cached_player_matches['live_match_game_id'] == live_match_details['gameId']:
        return False

    logging.info(f"live_match_details={live_match_details}, cached_player_matches={cached_player_matches}")
    return True


def has_elapsed(start_time: int, end_time: int, minutes: int) -> bool:
    time_difference_seconds = end_time - start_time
    minutes_in_seconds = minutes * 60
    return time_difference_seconds >= minutes_in_seconds


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        logging.error(e)
    logging.info(f'Bot is ready. Logged in as {bot.user}')

    await asyncio.create_task(update_accounts())


@bot.tree.command(name="set-betting-channel", description="Set the betting channel")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_betting_channel(interaction: discord.Interaction):
    await interaction.response.defer()
    guild = get_guild_by_guild_id(interaction.guild.id)
    if not guild:
        guild = create_guild(interaction.guild.id)

    guild.channel_id = interaction.channel.id
    await interaction.followup.send(f'Betting channel has been set to {interaction.channel.mention}.')


@bot.tree.command(name="set-currency", description="Set the currency for the guild")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_currency(interaction: discord.Interaction, currency: str):
    await interaction.response.defer()
    guild = get_guild_by_guild_id(interaction.guild.id)
    if not guild:
        guild = create_guild(interaction.guild.id)

    guild.currency = currency
    await interaction.followup.send(f'Currency has been set to {currency}.')


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
    await interaction.response.defer()

    if "#" not in riot_id:
        await interaction.followup.send("Invalid format. The Riot ID must be in the format `USERNAME#TAGLINE`.")
        return

    username, tag_line = riot_id.split("#", 1)

    try:
        # Step 1: Get account by Riot ID
        account_info = await get_account_by_riot_id(username, tag_line, region.value)
        if 'status' in account_info and account_info['status']['status_code'] != 200:
            await interaction.followup.send(f"Error: {account_info['status']['message']}")
            return

        puuid = account_info.get('puuid')
        if not puuid:
            await interaction.followup.send("Could not retrieve PUUID from the provided Riot ID.")
            return

        # Step 2: Get summoner by PUUID
        summoner_info = await get_summoner_by_puuid(puuid, region.value)
        if 'status' in summoner_info and summoner_info['status']['status_code'] != 200:
            await interaction.followup.send(f"Error: {summoner_info['status']['message']}")
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
        await interaction.followup.send(f'Riot ID: "{riot_id}" on {region.name} has been set.')

    except Exception as e:
        logging.error(f"Error processing League of Legends account: {e}")
        await interaction.followup.send(
            "An error occurred while setting the League of Legends account. Please try again later.")


@bot.tree.command(name="wallet", description="Check the amount of currency in your wallet")
async def wallet(interaction: discord.Interaction):
    await interaction.response.defer()

    user = get_user_by_discord_account_id(interaction.user.id)
    if not user:
        user = create_user(interaction.user.id)

    guild = get_guild_by_guild_id(interaction.guild.id)
    if not guild:
        guild = create_guild(interaction.guild.id)

    bank = services.db.query(Bank).filter_by(user_id=user.id, guild_id=guild.id).first()
    if not bank:
        bank = create_bank(user.id, guild.id)

    await interaction.followup.send(f'You have {bank.coins} {guild.currency} in your wallet.')


@bot.tree.command(name="bet", description="Bet on the outcome of the current game")
async def bet(interaction: discord.Interaction, discord_user: discord.User):
    await interaction.response.defer(ephemeral=True)

    logging.info(f"Received bet command from user {interaction.user.id} for target user {discord_user.id}")

    # Fetch or create the user
    user = get_user_by_discord_account_id(interaction.user.id)
    if not user:
        logging.info(f"No user found for {interaction.user.id}. Creating new user.")
        user = create_user(discord_user.id)

    # Fetch or create the target user
    target_user = get_user_by_discord_account_id(discord_user.id)
    if not target_user:
        logging.info(f"No target user found for {discord_user.id}. Creating new user.")
        target_user = create_user(discord_user.id)
        return

    # Fetch the guild information
    guild = get_guild_by_guild_id(interaction.guild.id)
    logging.debug(f"Retrieved guild information for {interaction.guild.id}: {guild}")

    # Get the League of Legends account for the target user
    target_league_of_legends_account = get_lol_account(target_user.id, guild.id)
    if not target_league_of_legends_account:
        logging.warning(f"Target user {discord_user.display_name} does not have a League of Legends account set.")
        await interaction.followup.send(
            f"{discord_user.display_name} does not have a League of Legends account set.",
            ephemeral=True
        )
        return

    # Check for active bets
    betting_info_for_target_user = active_bets.get(target_league_of_legends_account.puuid, None)
    if not betting_info_for_target_user:
        logging.warning(f"Target user {discord_user.display_name} does not have an active bet.")
        await interaction.followup.send(
            f"{discord_user.display_name} does not have an active bet.",
            ephemeral=True
        )
        return

    # Check if the bet has expired
    game_start_time = betting_info_for_target_user.get('start_time')
    current_time = int(time.time())

    logging.debug(f"Game start time: {game_start_time}, current time: {current_time}")

    if has_elapsed(game_start_time, current_time, 2):
        logging.info(f"Bet for {discord_user.display_name} has expired.")
        await interaction.followup.send(
            f"Bet for {discord_user.display_name} has expired.",
            ephemeral=True
        )
        return

    # Create a bet view and send it to the user
    view = BetView(account=target_league_of_legends_account, player_bets=betting_info_for_target_user)
    logging.info(f"Sending bet view to user {interaction.user.id}")
    await interaction.followup.send("Place your bet:", view=view, ephemeral=True)


class BetView(View):
    def __init__(self, account: LeagueOfLegendsAccount, player_bets):
        super().__init__(timeout=None)
        self.account = account
        self.player_bets = player_bets
        self.amount = 0
        self.current_operation_is_add = True
        self.outcome_win = None

    async def update_message(self, interaction: discord.Interaction):
        self.amount_button.label = f"{self.amount}"

        if self.current_operation_is_add is True:
            self.add.style = discord.ButtonStyle.success
            self.subtract.style = discord.ButtonStyle.secondary
        elif self.current_operation_is_add is False:
            self.add.style = discord.ButtonStyle.secondary
            self.subtract.style = discord.ButtonStyle.success

        if self.outcome_win is True:
            self.bet_win.style = discord.ButtonStyle.success
            self.bet_lose.style = discord.ButtonStyle.secondary
        elif self.outcome_win is False:
            self.bet_win.style = discord.ButtonStyle.secondary
            self.bet_lose.style = discord.ButtonStyle.success

        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='-', style=discord.ButtonStyle.secondary, row=0)
    async def subtract(self, interaction: discord.Interaction, button: Button):
        self.current_operation_is_add = False
        await self.update_message(interaction)

    @discord.ui.button(label='0', style=discord.ButtonStyle.secondary, row=0, disabled=True)
    async def amount_button(self, interaction: discord.Interaction, button: Button):
        pass

    @discord.ui.button(label='+', style=discord.ButtonStyle.secondary, row=0)
    async def add(self, interaction: discord.Interaction, button: Button):
        self.current_operation_is_add = True
        await self.update_message(interaction)

    @discord.ui.button(label='1', style=discord.ButtonStyle.secondary, row=1)
    async def add1(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount += 1
        else:
            self.amount = max(0, self.amount - 1)
        await self.update_message(interaction)

    @discord.ui.button(label='5', style=discord.ButtonStyle.secondary, row=1)
    async def add5(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount += 5
        else:
            self.amount = max(0, self.amount - 5)
        await self.update_message(interaction)

    @discord.ui.button(label='10', style=discord.ButtonStyle.secondary, row=1)
    async def add10(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount += 10
        else:
            self.amount = max(0, self.amount - 10)
        await self.update_message(interaction)

    @discord.ui.button(label='25', style=discord.ButtonStyle.secondary, row=1)
    async def add25(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount += 25
        else:
            self.amount = max(0, self.amount - 25)
        await self.update_message(interaction)

    @discord.ui.button(label='Win', style=discord.ButtonStyle.secondary, row=2)
    async def bet_win(self, interaction: discord.Interaction, button: Button):
        self.outcome_win = True
        await self.update_message(interaction)

    @discord.ui.button(label='Lose', style=discord.ButtonStyle.secondary, row=2)
    async def bet_lose(self, interaction: discord.Interaction, button: Button):
        target_discord_id = self.account.user.discord_account_id
        better_discord_id = interaction.user.id
        logging.info(f"Target Discord ID: {target_discord_id}, Better Discord ID: {better_discord_id}")
        if target_discord_id == better_discord_id:
            button.disabled = True
            return
        self.outcome_win = False
        await self.update_message(interaction)

    @discord.ui.button(label='Lock In', style=discord.ButtonStyle.primary, row=3)
    async def lock_in(self, interaction: discord.Interaction, button: Button):
        logging.info(f"User {interaction.user.id} attempted to lock in a bet.")

        game_start_time = self.player_bets.get('start_time')
        current_time = int(time.time())

        if has_elapsed(game_start_time, current_time, 2):
            logging.warning(f"Bet expired for user {interaction.user.id}. Game start time: {game_start_time}, current "
                            f"time: {current_time}.")
            await interaction.response.send_message(
                "Bet has expired.",
                ephemeral=True
            )
            return

        user = get_user_by_discord_account_id(interaction.user.id)

        bank = get_bank_by_user_and_guild(user.id, self.account.guild.id)
        if not bank:
            bank = create_bank(user.id, self.account.guild.id)

        if 0 < self.amount <= bank.coins and self.outcome_win is not None:
            wager = {
                'discord_id': user.id,
                'server_id': self.account.guild.id,
                'wagered_win': self.outcome_win,
                'wagered_amount': self.amount
            }
            self.player_bets['bets'].append(wager)
            set_bank_coins(user.id, self.account.guild.id, bank.coins - self.amount)
            logging.info(
                f"Bet locked in for user {interaction.user.id}: Amount: {self.amount} {self.account.guild.currency}, "
                f"Outcome: {'Win' if self.outcome_win else 'Lose'}.")
            await interaction.response.send_message(
                f"Bet locked in: {self.amount} on {'Win' if self.outcome_win else 'Lose'}",
                ephemeral=True
            )
            self.stop()
        else:
            logging.warning(
                f"Bet lock-in failed for user {interaction.user.id}. Amount: {self.amount}, Outcome: {self.outcome_win}.")
            await interaction.response.send_message(
                "You must choose an affordable amount and an outcome to lock in the bet.",
                ephemeral=True
            )


async def send_match_start_discord_message(account: LeagueOfLegendsAccount, match_details, timeout=3):
    guild_id = account.guild.guild_id
    channel_id = account.guild.channel_id
    logging.info("Entering function")
    logging.info(f"guild_id={guild_id}, channel_id={channel_id}")

    try:
        guild = discord.utils.get(bot.guilds, id=guild_id)
        logging.info(f"guild={guild}")

        if guild:
            channel = bot.get_channel(channel_id)
            logging.info(f"channel={channel}")

            if channel:
                player_active_bets = active_bets.get(account.puuid)
                logging.info(f"bet={player_active_bets}")

                discord_user = await bot.fetch_user(account.user.discord_account_id)
                logging.info(f"discord_user={discord_user}")

                name = discord_user.display_name
                pfp = discord_user.display_avatar
                riot_account = await get_account_info_by_puuid(account.puuid, account.region)
                riot_id = riot_account.get('gameName')
                logging.info(f"name={name}, pfp={pfp}, riot_id={riot_id}")

                for participant in match_details['participants']:
                    logging.info(f"participant={participant}")

                    if participant['puuid'] == account.puuid:
                        champion_id = participant['championId']
                        champion_icon = await get_champion_icon(champion_id)
                        logging.info(f"champion_id={champion_id}, champion_icon={champion_icon}")

                        message = discord.Embed(title=f"Game started for {riot_id}")
                        message.set_author(name=name, icon_url=pfp)
                        message.set_thumbnail(url=champion_icon)
                        message.add_field(name="Win odds", value=player_active_bets['win_odds'])
                        message.add_field(name="Lose odds", value=player_active_bets['lose_odds'])

                        logging.info("Sending message to channel")
                        await asyncio.wait_for(channel.send(embed=message), timeout)
                        logging.info("Message sent successfully")

    except asyncio.TimeoutError:
        logging.error(f"Sending message timed out after {timeout} seconds")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


async def update_accounts():
    while True:
        await update_league_of_legends_accounts()
        await asyncio.sleep(3)
