from the_house.config import DISCORD_TOKEN
from the_house.services import services


if __name__ == '__main__':
    services.bot.run(DISCORD_TOKEN)
