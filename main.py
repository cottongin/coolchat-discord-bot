import discord
intents = discord.Intents.default()
intents.members = True
intents.presences = True
from discord.ext import commands

import os, sys, traceback
import logging
import coloredlogs

from dotenv import dotenv_values, load_dotenv
import redis

try:
    # dev build only requires this
    load_dotenv('.env')
    dev_bot = os.getenv("DEVBOT")
    environvars = os.environ
    logger = logging.getLogger('discord')
    logger.setLevel(logging.DEBUG)
    handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    logger.addHandler(handler)
except:
    # heroku stores this
    dev_bot = False
    environvars = os.environ

# LOGGER = logging.getLogger(__name__)
# coloredlogs.install(level='DEBUG', logger=LOGGER,
#     fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
#     datefmt='%Y-%m-%d %H:%M:%S',
#     style='{'
# )

class Bot(commands.Bot):
    def __init__(self, **kwargs):
        super().__init__(
            command_prefix=kwargs.pop('command_prefix'),
            description=kwargs.pop('description'),
            case_insensitive=kwargs.pop('case_insensitive'),
            intents=kwargs.pop('intents')

        )

        try:
            self.db = redis.from_url(
                os.environ.get("REDIS_URL"),
                socket_timeout=3
            )
        except Exception as e:
            LOGGER.error(e)
            self.db = {}
            pass

        self.environs = environvars

def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    if not dev_bot:
        prefixes = ['`', '!', '?']
    else:
        prefixes = ['.']

    return commands.when_mentioned_or(*prefixes)(bot, message)


initial_extensions = [
    'cogs.owner',
    'cogs.sports',
    'cogs.golf',
    'cogs.mma',
    'cogs.misc',
    'cogs.mock',
    'cogs.weather',
    'cogs.scores',
    'cogs.stridekick'
]

bot = Bot(command_prefix=get_prefix, description='A Cool Chat Bot', case_insensitive=True, intents=intents)
# bot = commands.Bot(command_prefix=get_prefix, description='A Cool Chat Bot', case_insensitive=True, intents=intents)

if __name__ == '__main__':
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            print(f'Failed to load extension {extension}.', file=sys.stderr)
            traceback.print_exc()


@bot.event
async def on_ready():
    """http://discordpy.readthedocs.io/en/rewrite/api.html#discord.on_ready"""

    print(f'\n\nLogged in as: {bot.user.name} - {bot.user.id}\nVersion: {discord.__version__}\n')

    game = discord.Activity(
        name="Making Balls Cool Again",
        type=discord.ActivityType.playing)
    await bot.change_presence(activity=game)
    print(f'Successfully logged in and booted...!')

token = os.getenv("DISCORD_BOT_SECRET")
bot.run(token, bot=True, reconnect=True)
