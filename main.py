import discord
from discord.ext import commands

import os, sys, traceback
import logging
import coloredlogs

from dotenv import load_dotenv
try:
    # dev build only requires this
    load_dotenv('.env')
    dev_bot = os.getenv("DEVBOT")
except:
    # heroku stores this
    dev_bot = False

LOGGER = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)

def get_prefix(bot, message):
    """A callable Prefix for our bot. This could be edited to allow per server prefixes."""

    if not dev_bot:
        prefixes = ['`', '!', '?']
    else:
        prefixes = ['.']

    return commands.when_mentioned_or(*prefixes)(bot, message)


initial_extensions = ['cogs.owner',
                      'cogs.sports',
                      'cogs.mma',
                      'cogs.misc',
                      'cogs.mock']

bot = commands.Bot(command_prefix=get_prefix, description='A Cool Chat Bot')

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
