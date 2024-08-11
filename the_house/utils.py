import asyncio
import logging
import time
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ui import View, Button

from models import LeagueOfLegendsAccount
from services import services

from db_utils import (
    create_user,
    get_user_by_user_table_id,
    get_user_by_discord_account_id,
    create_guild,
    create_bank,
    get_bank_by_user_and_guild,
    get_guild_by_guild_id,
    set_lol_account,
    get_lol_account,
    set_bank_coins,
    get_banks_sorted_by_coins_for_guild,
    get_all_banks,
    increment_multiple_bank_coins,
    get_all_league_of_legends_accounts
)

from lol_api_utils import (
    get_account_by_riot_id,
    get_account_info_by_puuid,
    get_summoner_by_puuid,
    get_match_ids_by_puuid,
    get_match_details,
    get_live_match_details,
    get_champion_icon
)

bot = services.bot

cached_league_of_legends_games = {}
active_bets = {}
last_execution_date = datetime.utcnow().date()


def calculate_sleep_times(num_accounts: int, requests_per_account: int = 3, max_requests_per_second: int = 20,
                          max_requests_per_2_minutes: int = 100):
    short_term_sleep = max(0.2, requests_per_account / max_requests_per_second)

    total_requests = num_accounts * requests_per_account

    total_processing_time = num_accounts * short_term_sleep

    if total_requests > max_requests_per_2_minutes:
        raise ValueError(f"Number of accounts exceeds the maximum requests allowed in 2 minutes")

    additional_time_needed = (120 * total_requests / max_requests_per_2_minutes) - total_processing_time

    long_term_sleep = max(0.0, additional_time_needed)

    return short_term_sleep, long_term_sleep


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


async def did_player_win(puuid: str, completed_match_details: dict) -> bool:
    logging.info("Checking if player won the match")
    logging.info(f"Player PUUID: {puuid}")

    participants = completed_match_details.get('info', {}).get('participants', [])
    logging.info(f"Number of participants in match: {len(participants)}")

    for participant in participants:
        logging.debug(f"Checking participant PUUID: {participant['puuid']}")

        if participant['puuid'] == puuid:
            if participant['win']:
                logging.info(f"Player {puuid} won the match")
            else:
                logging.info(f"Player {puuid} lost the match")

            return participant['win']

    logging.warning(f"Player with PUUID {puuid} not found in match participants")
    return False


async def payout_winners(player_bets: dict, result_win: bool):
    logging.info(f"player_bets={player_bets}, result_win={result_win}")
    win_odds = player_bets['win_odds']
    lose_odds = player_bets['lose_odds']

    logging.info("Starting payout process")
    logging.info(f"Win odds: {win_odds}, Lose odds: {lose_odds}, Result win: {result_win}")

    for individual_bet in player_bets['bets']:
        payout = 0
        discord_id = individual_bet['discord_id']
        server_id = individual_bet['server_id']
        wagered_amount = individual_bet['wagered_amount']
        wagered_win = individual_bet['wagered_win']

        logging.info(f"Processing bet for Discord ID: {discord_id}")
        logging.info(f"Wagered amount: {wagered_amount}, Wagered win: {wagered_win}")

        user = get_user_by_user_table_id(discord_id)
        bank = get_bank_by_user_and_guild(discord_id, server_id)

        logging.info(f"Retrieved user with ID: {user.id}")
        logging.info(f"Current bank coins: {bank.coins}")

        if wagered_win == result_win:
            payout = round(wagered_amount * (win_odds if wagered_win else lose_odds), 2)
            logging.info(f"Bet result matches the game result. Calculated payout: {payout}")
        else:
            logging.info("Bet result does not match the game result. No payout.")

        logging.info(f"Paying out {payout} coins to user ID: {user.id}")

        set_bank_coins(user.id, server_id, bank.coins + payout)
        logging.info(f"Updated bank coins for user ID: {user.id} to {bank.coins + payout}")

    logging.info("Payout process completed")


async def refund_bets(player_bets: dict):
    logging.info("Starting refund process")
    for individual_bet in player_bets['bets']:
        discord_id = individual_bet['discord_id']
        server_id = individual_bet['server_id']
        wagered_amount = individual_bet['wagered_amount']

        user = get_user_by_user_table_id(discord_id)
        bank = get_bank_by_user_and_guild(discord_id, server_id)

        logging.info(f"Refunding {wagered_amount} coins to user ID: {user.id}")
        set_bank_coins(user.id, server_id, bank.coins + wagered_amount)
        logging.info(f"Updated bank coins for user ID: {user.id} to {bank.coins + wagered_amount}")

    logging.info("Refund process completed")


async def update_league_of_legends_accounts(short_sleep_time: float, accounts: list[LeagueOfLegendsAccount]):
    logging.info(f"Current bets = {active_bets}")

    for account in accounts:
        try:
            await asyncio.sleep(short_sleep_time)
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
        logging.warning(f"Could not get live match details for puuid {puuid}: {e}")
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
        game_start_time = time.time()
        win_odds, lose_odds = await calculate_odds(puuid, region, queue_id=queue_id)
        logging.info(f"queue_id={queue_id}, win_odds={win_odds}, lose_odds={lose_odds}")
        active_bets[puuid] = {
            'win_odds': win_odds,
            'lose_odds': lose_odds,
            'start_time': game_start_time,
            'bets': []
        }
        await send_match_start_discord_message(account, live_match_details)
        logging.info(f"Sent match start message for puuid {puuid}")

    elif await league_of_legends_account_just_end_game(live_match_details, previous_match_details,
                                                       puuid) and puuid in active_bets:
        logging.info(f"Match ended for puuid {puuid}")
        if len(active_bets[puuid]['bets']) > 0:
            did_remake_happen = previous_match_info['participants'][0]['gameEndedInEarlySurrender']
            if did_remake_happen:
                await refund_bets(active_bets[puuid])
                logging.info(f"Remake happened for puuid {puuid}")
            else:
                result_win = await did_player_win(puuid, previous_match_details)
                await payout_winners(active_bets[puuid], result_win)
                await send_match_end_discord_message(account, result_win, active_bets[puuid])
        active_bets.pop(puuid)

    cached_league_of_legends_games[puuid] = {
        'previous_match_game_id': previous_match_game_id,
        'live_match_game_id': live_match_game_id
    }


async def league_of_legends_account_just_start_game(live_match_details: dict, puuid: str) -> bool:
    if not live_match_details:
        return False

    cached_player_matches = cached_league_of_legends_games.get(puuid, None)

    if not cached_player_matches or cached_player_matches.get('live_match_game_id', None) == live_match_details.get(
            'gameId', None):
        return False

    logging.info(f"cached_player_matches={cached_player_matches}")
    return True


async def league_of_legends_account_just_end_game(live_match_details: dict, previous_match_details: dict,
                                                  puuid: str) -> bool:
    if live_match_details:
        return False

    cached_player_matches = cached_league_of_legends_games.get(puuid, None)

    if not cached_player_matches or cached_player_matches.get('live_match_game_id', None) == live_match_details.get(
            'gameId', None):
        return False

    logging.info(f"cached_player_matches={cached_player_matches}")
    return True


def has_elapsed(start_time: int, end_time: int, minutes: int) -> bool:
    time_difference_seconds = (end_time - start_time)
    minutes_in_seconds = minutes * 60

    logging.info(f"start_time={start_time}, end_time={end_time}, time_difference_seconds={time_difference_seconds}")

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

    bank = get_bank_by_user_and_guild(user.id, guild.id)
    if not bank:
        bank = create_bank(user.id, guild.id)

    await interaction.followup.send(f'You have {bank.coins:.2f} {guild.currency} in your wallet.')


@bot.tree.command(name="leaderboard", description="Check the leaderboard for the guild")
async def leaderboard(interaction: discord.Interaction):
    await interaction.response.defer()

    guild = get_guild_by_guild_id(interaction.guild.id)
    if not guild:
        guild = create_guild(interaction.guild.id)

    banks = get_banks_sorted_by_coins_for_guild(guild.id)

    if not banks:
        await interaction.followup.send("No banks found in this server.")
        return

    server_name = await bot.fetch_guild(guild.guild_id)

    embed = discord.Embed(
        title=f"{server_name} Leaderboard",
        description=f"🏆 **Top users by {guild.currency}** 🏆",
        color=discord.Color.gold()
    )

    for i, bank in enumerate(banks[:10]):
        discord_user = await bot.fetch_user(bank.user.discord_account_id)
        user_name = discord_user.display_name
        embed.add_field(
            name=f"{i + 1}. {user_name}",
            value=f"{bank.coins:.2f} {guild.currency}",
            inline=False
        )

    await interaction.followup.send(embed=embed)


@bot.tree.command(name="help", description="Show all available commands")
async def help_command(interaction: discord.Interaction):
    embed = discord.Embed(title="Bot Commands", description="List of all available commands",
                          color=discord.Color.blue())

    commands = {
        "set-betting-channel": "Set the betting channel",
        "set-currency": "Set the currency for the guild",
        "set-league-of-legends-account": "Set a linked League of Legends account (one per Discord user)",
        "wallet": "Check the amount of currency in your wallet",
        "leaderboard": "Check the leaderboard for the guild",
        "bet": "Bet on the outcome of the current game (expires after 4 minutes)",
        "report": "Report an issue with the bot"
    }
    embed.add_field(name="Profile picture icon created by Ralf Schmitzer - Flaticon", value="https://www.flaticon.com"
                                                                                            "/free-icons/groupier?",
                    inline=False)
    for command, description in commands.items():
        embed.add_field(name=f"/{command}", value=description, inline=False)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="report", description="Report an issue with the bot")
async def report_command(interaction: discord.Interaction):
    embed = discord.Embed(
        title="Report an Issue",
        description=(
            "If you encounter any issues or have suggestions, please report them on our GitHub issues page. "
            "You'll need to create a GitHub account if you don't have one already.\n\n"
            "[GitHub Issues Page](https://github.com/zainaraza43/the-house/issues)"
        ),
        color=discord.Color.red()
    )
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="bet", description="Bet on the outcome of the current game")
async def bet(interaction: discord.Interaction, discord_user: discord.User):
    await interaction.response.defer(ephemeral=True)

    can_create_ui, message = await can_create_bet_view(interaction, discord_user)

    if can_create_ui:
        view = await create_bet_view(interaction, discord_user)
        await interaction.followup.send("Place your bet:", view=view, ephemeral=True)
    else:
        await interaction.followup.send(message, ephemeral=True)


class BetView(View):
    def __init__(self, league_account: LeagueOfLegendsAccount, player_bets, gambler_discord_account, gambler_bank):
        super().__init__(timeout=None)
        self.account = league_account
        self.player_bets = player_bets
        self.amount = 0
        self.current_operation_is_add = True
        self.outcome_win = None
        self.user = gambler_discord_account
        self.bank = gambler_bank

    async def update_message(self, interaction: discord.Interaction):
        self.amount_button.label = f"{self.amount:.2f}"

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

    @discord.ui.button(label='+', style=discord.ButtonStyle.success, row=0)
    async def add(self, interaction: discord.Interaction, button: Button):
        self.current_operation_is_add = True
        await self.update_message(interaction)

    @discord.ui.button(label='1', style=discord.ButtonStyle.secondary, row=1)
    async def add1(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount = min(self.bank.coins, self.amount + 1)
        else:
            self.amount = max(0, self.amount - 1)
        await self.update_message(interaction)

    @discord.ui.button(label='5', style=discord.ButtonStyle.secondary, row=1)
    async def add5(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount = min(self.bank.coins, self.amount + 5)
        else:
            self.amount = max(0, self.amount - 5)
        await self.update_message(interaction)

    @discord.ui.button(label='10', style=discord.ButtonStyle.secondary, row=1)
    async def add10(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount = min(self.bank.coins, self.amount + 10)
        else:
            self.amount = max(0, self.amount - 10)
        await self.update_message(interaction)

    @discord.ui.button(label='25', style=discord.ButtonStyle.secondary, row=1)
    async def add25(self, interaction: discord.Interaction, button: Button):
        if self.current_operation_is_add:
            self.amount = min(self.bank.coins, self.amount + 25)
        else:
            self.amount = max(0, self.amount - 25)
        await self.update_message(interaction)

    @discord.ui.button(label='All In', style=discord.ButtonStyle.danger, row=1)
    async def all_in(self, interaction: discord.Interaction, button: Button):
        self.amount = self.bank.coins
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
            await interaction.response.send_message(
                "You cannot bet against yourself.",
                ephemeral=True
            )
            button.disabled = True
            return
        self.outcome_win = False
        await self.update_message(interaction)

    @discord.ui.button(label='Lock In', style=discord.ButtonStyle.primary, row=3)
    async def lock_in(self, interaction: discord.Interaction, button: Button):
        logging.info(f"User {interaction.user.id} attempted to lock in a bet.")

        game_start_time = self.player_bets.get('start_time')
        current_time = int(time.time())

        if has_elapsed(game_start_time, current_time, 4):
            logging.warning(f"Bet expired for user {interaction.user.id}. Game start time: {game_start_time}, current "
                            f"time: {current_time}.")
            await interaction.response.send_message(
                "Bet has expired.",
                ephemeral=True
            )
            return

        if 0 < self.amount <= self.bank.coins and self.outcome_win is not None:
            wager = {
                'discord_id': self.user.id,
                'server_id': self.account.guild.id,
                'wagered_win': self.outcome_win,
                'wagered_amount': self.amount
            }
            self.player_bets['bets'].append(wager)
            set_bank_coins(self.user.id, self.account.guild.id, self.bank.coins - self.amount)
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


async def can_create_bet_view(interaction: discord.Interaction, discord_user: discord.User) -> tuple[bool, str]:
    logging.info(f"Received bet command from user {interaction.user.id} for target user {discord_user.id}")

    # Fetch or create the user
    user = get_user_by_discord_account_id(interaction.user.id)
    if not user:
        logging.info(f"No user found for {interaction.user.id}. Creating new user.")
        user = create_user(interaction.user.id)

    # Fetch or create the target user
    target_user = get_user_by_discord_account_id(discord_user.id)
    if not target_user:
        error_message = (f"No target user found for {discord_user.id}. They do not have a League of Legends account "
                         f"registered")
        logging.info(error_message)
        return False, error_message

        # Fetch the guild information
    guild = get_guild_by_guild_id(interaction.guild.id)
    logging.debug(f"Retrieved guild information for {interaction.guild.id}: {guild}")

    # Get the League of Legends account for the target user
    target_league_of_legends_account = get_lol_account(target_user.id, guild.id)
    if not target_league_of_legends_account:
        error_message = f"Target user {discord_user.display_name} does not have a League of Legends account set."
        logging.warning(error_message)
        return False, error_message

    # Check for active bets
    betting_info_for_target_user = active_bets.get(target_league_of_legends_account.puuid, None)
    if not betting_info_for_target_user:
        error_message = f"Target user {discord_user.display_name} does not have an active bet."
        logging.warning(error_message)
        return False, error_message

    # Check if the bet has expired
    game_start_time = betting_info_for_target_user.get('start_time')
    current_time = int(time.time())

    logging.debug(f"Game start time: {game_start_time}, current time: {current_time}")

    if has_elapsed(game_start_time, current_time, 4):
        error_message = f"Bet for {discord_user.display_name} has expired."
        logging.info(error_message)
        return False, error_message

    logging.info(f"Sending bet view to user {interaction.user.id}")
    return True, ""


async def create_bet_view(interaction: discord.Interaction, discord_user: discord.User) -> BetView:
    user = get_user_by_discord_account_id(interaction.user.id)
    target_user = get_user_by_discord_account_id(discord_user.id)
    guild = get_guild_by_guild_id(interaction.guild.id)
    target_league_of_legends_account = get_lol_account(target_user.id, guild.id)
    betting_info_for_target_user = active_bets.get(target_league_of_legends_account.puuid, None)

    bank = get_bank_by_user_and_guild(user.id, guild.id)
    if not bank:
        bank = create_bank(user.id, guild.id)

    view = BetView(league_account=target_league_of_legends_account, player_bets=betting_info_for_target_user,
                   gambler_discord_account=user, gambler_bank=bank)
    return view


class BetButtonView(View):
    def __init__(self, account: LeagueOfLegendsAccount):
        super().__init__(timeout=None)
        self.account = account

    @discord.ui.button(label="Place Bet", style=discord.ButtonStyle.primary)
    async def place_bet_button(self, interaction: discord.Interaction, button: Button):
        interaction.response.defer()
        discord_user = await bot.fetch_user(self.account.user.discord_account_id)

        can_create_ui, message = await can_create_bet_view(interaction, discord_user)

        if can_create_ui:
            view = await create_bet_view(interaction, discord_user)
            await interaction.response.send_message("Place your bet:", view=view, ephemeral=True)
        else:
            await interaction.response.send_message(message, ephemeral=True)


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

                        bet_view = BetButtonView(account)

                        logging.info("Sending message to channel")
                        await asyncio.wait_for(channel.send(embed=message, view=bet_view), timeout)
                        logging.info("Message sent successfully")

    except asyncio.TimeoutError:
        logging.error(f"Sending message timed out after {timeout} seconds")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


async def send_match_end_discord_message(account: LeagueOfLegendsAccount, result_win: bool, bet_info: dict,
                                         timeout=3):
    guild_id = account.guild.guild_id
    channel_id = account.guild.channel_id

    try:
        guild = discord.utils.get(bot.guilds, id=guild_id)
        if guild:
            channel = bot.get_channel(channel_id)
            if channel:
                target_discord_user = await bot.fetch_user(account.user.discord_account_id)
                name = target_discord_user.display_name
                pfp = target_discord_user.display_avatar
                riot_account = await get_account_info_by_puuid(account.puuid, account.region)
                riot_id = riot_account.get('gameName')

                message = discord.Embed(title=f"Game ended for {riot_id}")
                message.set_author(name=name, icon_url=pfp)
                bets_list = bet_info['bets']

                for individual_bet in bets_list:
                    user = get_user_by_user_table_id(individual_bet['discord_id'])
                    discord_user = await bot.fetch_user(user.discord_account_id)
                    currency = account.guild.currency
                    name = discord_user.display_name
                    wagered_amount = individual_bet['wagered_amount']
                    wagered_win = individual_bet['wagered_win']
                    win_odds = bet_info['win_odds']
                    lose_odds = bet_info['lose_odds']

                    logging.debug(f"Processing bet for user {name} (ID: {individual_bet['discord_id']}). "
                                  f"Wagered {wagered_amount} {currency} on {'Win' if wagered_win else 'Lose'}.")

                    if wagered_win == result_win:
                        if result_win:
                            message.add_field(name=f"{name} bet",
                                              value=f"{wagered_amount} {currency} on Win: Won **{wagered_amount * win_odds} {currency}**",
                                              inline=False)
                        else:
                            message.add_field(name=f"{name} bet",
                                              value=f"{wagered_amount} {currency} on Lose: Won **{wagered_amount * lose_odds} {currency}**",
                                              inline=False)
                    else:
                        message.add_field(name=f"{name} bet",
                                          value=f"{wagered_amount} {currency} on {'Win' if wagered_win else 'Lose'}: "
                                                f"Lost **{wagered_amount} {currency}**", inline=False)

                await asyncio.wait_for(channel.send(embed=message), timeout)

    except asyncio.TimeoutError:
        logging.error(f"Sending message timed out after {timeout} seconds")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


async def update_accounts():
    while True:
        give_daily_coins()
        league_of_legends_accounts = get_all_league_of_legends_accounts()
        short_term_sleep, long_term_sleep = calculate_sleep_times(len(league_of_legends_accounts))
        logging.info(
            f"number of league of legends accounts ={len(league_of_legends_accounts)} short_term_sleep={short_term_sleep}, long_term_sleep={long_term_sleep}")
        await update_league_of_legends_accounts(short_term_sleep, league_of_legends_accounts)
        await asyncio.sleep(long_term_sleep)


def is_new_day_utc() -> bool:
    global last_execution_date
    current_date = datetime.utcnow().date()

    if last_execution_date is None or last_execution_date < current_date:
        last_execution_date = current_date
        return True

    return False


def give_daily_coins():
    if is_new_day_utc():
        logging.info("New day detected, distributing daily coins...")
        banks = get_all_banks()
        increment_multiple_bank_coins(banks, 10)
        logging.info(f"Distributed 10 daily coins to {len(banks)} users.")
