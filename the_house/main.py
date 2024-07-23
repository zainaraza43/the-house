import asyncio
import logging
import threading

import discord
from discord import app_commands
from discord.ext import commands

from config import DISCORD_TOKEN
from utils import get_account_by_riot_id, get_summoner_by_puuid, set_lol_account, create_user, create_guild, \
    get_user_by_discord_account_id, get_guild_by_guild_id, update_lol_accounts

intents = discord.Intents.default()
intents.message_content = True

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
async def on_ready():
    try:
        await bot.tree.sync()
    except Exception as e:
        print(e)
    print(f'Bot is ready. Logged in as {bot.user}')

    start_updating_thread()


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


def start_updating_accounts_task(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(update_accounts())


async def update_accounts():
    while True:
        await update_lol_accounts()
        await asyncio.sleep(5)


def start_updating_thread():
    loop = asyncio.new_event_loop()
    t = threading.Thread(target=start_updating_accounts_task, args=(loop,))
    t.start()


if __name__ == '__main__':
    bot.run(DISCORD_TOKEN)
