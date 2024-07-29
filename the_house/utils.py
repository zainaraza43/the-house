import asyncio
import logging

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
    format='%(asctime)s - %(levelname)s - %(funcName)s - %(message)s'
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


def create_bank(user_id: int, guild_id: int):
    db = services.db
    bank = Bank(user_id=user_id, guild_id=guild_id)
    db.add(bank)
    db.commit()
    return bank


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


async def get_match_ids_by_puuid(puuid: str, region: str, start=0, count=1, queue_id=None) -> list:
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


async def update_lol_accounts():
    db = services.db
    accounts = db.query(LeagueOfLegendsAccount).all()

    for account in accounts:
        try:
            match_ids = await get_match_ids_by_puuid(account.puuid, region=account.region, count=1)
            last_match_id = match_ids[0]
            match_details = await get_match_details(last_match_id, account.region)
            last_match_game_id = match_details['info']['gameId']

            live_match_details = await get_live_match_details(account.puuid, account.region)
            live_match_game_id = live_match_details.get('gameId', None)

            if lol_accounts.get(account.puuid, None) is not None:
                if not live_match_game_id:
                    # game just ended
                    if lol_accounts.get(account.puuid).get('live_match', None) == last_match_game_id:
                        logging.info(
                            f"Game just ended for {account.puuid} ({lol_accounts[account.puuid]} == {last_match_game_id})")
                        # await send_match_start_discord_message(account.guild.guild_id, account.guild.channel_id,
                        #                                        f"Game just ended for <@{account.user.discord_account_id}>")
                else:
                    # game just started
                    if lol_accounts.get(account.puuid).get('live_match', None) != live_match_game_id:
                        logging.info(
                            f"Game just started for {account.puuid} ({lol_accounts[account.puuid]} != {live_match_game_id})")
                        queue_id = live_match_details['gameQueueConfigId']
                        win_odds, lose_odds = calculate_odds(account.puuid, account.region, queue_id)
                        new_game_bet = {
                            "game_id": live_match_game_id,
                            "match_id": None,
                            "win_odds": win_odds,
                            "lose_odds": lose_odds,
                            "bets": {}
                        }
                        bets[account.puuid] = new_game_bet
                        await send_match_start_discord_message(account, live_match_details)

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
    await interaction.response.defer(ephemeral=True)
    guild = get_guild_by_guild_id(interaction.guild.id)
    if not guild:
        guild = create_guild(interaction.guild.id)

    guild.channel_id = interaction.channel.id
    await interaction.followup.send(f'Betting channel has been set to {interaction.channel.mention}.')


@bot.tree.command(name="set-currency", description="Set the currency for the guild")
@app_commands.checks.has_permissions(manage_guild=True)
async def set_currency(interaction: discord.Interaction, currency: str):
    await interaction.response.defer(ephemeral=True)
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
    await interaction.response.defer(ephemeral=True)

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
    await interaction.response.defer(ephemeral=True)

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


class BetView(View):
    def __init__(self, account: LeagueOfLegendsAccount, bet):
        super().__init__(timeout=None)
        self.account = account
        self.bet = bet
        self.amount = 0
        self.current_operation_is_add = True
        self.outcome_win = None

    async def interaction_check(self, interaction: discord.Interaction):
        return interaction.user.id == self.account.id

    async def update_message(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.set_field_at(2, name="Amount Bet", value=f"{self.amount}")
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label='+', style=discord.ButtonStyle.primary, row=0)
    async def add(self, button: Button, interaction: discord.Interaction):
        self.current_operation_is_add = True
        await self.update_message(interaction)

    @discord.ui.button(label='-', style=discord.ButtonStyle.primary, row=0)
    async def subtract(self, button: Button, interaction: discord.Interaction):
        self.current_operation_is_add = False
        await self.update_message(interaction)

    @discord.ui.button(label='1', style=discord.ButtonStyle.secondary, row=1)
    async def add1(self, button: Button, interaction: discord.Interaction):
        if self.current_operation_is_add:
            self.amount += 1
        else:
            self.amount = max(0, self.amount - 1)
        await self.update_message(interaction)

    @discord.ui.button(label='5', style=discord.ButtonStyle.secondary, row=1)
    async def add5(self, button: Button, interaction: discord.Interaction):
        if self.current_operation_is_add:
            self.amount += 5
        else:
            self.amount = max(0, self.amount - 5)
        await self.update_message(interaction)

    @discord.ui.button(label='10', style=discord.ButtonStyle.secondary, row=1)
    async def add10(self, button: Button, interaction: discord.Interaction):
        if self.current_operation_is_add:
            self.amount += 10
        else:
            self.amount = max(0, self.amount - 10)
        await self.update_message(interaction)

    @discord.ui.button(label='25', style=discord.ButtonStyle.secondary, row=1)
    async def add25(self, button: Button, interaction: discord.Interaction):
        if self.current_operation_is_add:
            self.amount += 25
        else:
            self.amount = max(0, self.amount - 25)
        await self.update_message(interaction)

    @discord.ui.button(label='Win', style=discord.ButtonStyle.success, row=2)
    async def bet_win(self, button: Button, interaction: discord.Interaction):
        self.outcome_win = True
        await self.update_message(interaction)

    @discord.ui.button(label='Lose', style=discord.ButtonStyle.danger, row=2)
    async def bet_lose(self, button: Button, interaction: discord.Interaction):
        self.outcome_win = False
        await self.update_message(interaction)

    @discord.ui.button(label='Lock In', style=discord.ButtonStyle.primary, row=3)
    async def lock_in(self, button: Button, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        if self.amount > 0 and self.outcome_win is not None:
            wager = {
                'discord_id': self.account.user.id,
                'server_id': self.account.guild.id,
                'wagered_win': self.outcome_win,
                'wagered_amount': self.amount
            }
            self.bet[self.account.puuid]['bets'].append(wager)
            await interaction.followup.send(f"Bet locked in: {self.amount} on {self.outcome_win}")
            self.stop()
        else:
            await interaction.followup.send("You must choose an amount and an outcome to lock in the bet.")


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
                bet = bets.get(account.puuid)
                logging.info(f"bet={bet}")

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
                        message.add_field(name="Win odds", value=bet['win_odds'])
                        message.add_field(name="Lose odds", value=bet['lose_odds'])

                        view = BetView(account=account, bet=bet)

                        logging.info("Sending message to channel")
                        await asyncio.wait_for(channel.send(embed=message, view=view), timeout)
                        logging.info("Message sent successfully")

    except asyncio.TimeoutError:
        logging.error(f"Sending message timed out after {timeout} seconds")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


async def update_accounts():
    while True:
        await update_lol_accounts()
        await asyncio.sleep(3)
