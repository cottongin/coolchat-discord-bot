import discord
from discord.ext import commands
import sys
import logging


class OwnerCog(commands.Cog, name="Owner Commands"):

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__
    
    # Hidden means it won't show up on the default help.
    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    async def load_cog(self, ctx, *, cog: str):
        """Command which Loads a Module.
        Remember to use dot path. e.g: cogs.owner"""

        try:
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='unload', hidden=True)
    @commands.is_owner()
    async def unload_cog(self, ctx, *, cog: str):
        """Command which Unloads a Module.
        Remember to use dot path. e.g: cogs.owner"""
        loaded_cogs = self.bot.cogs
        if not cog.startswith('cogs.'):
            cog = "cogs." + cog

        targeted_cog = None
        for lcogs,lcogsv in loaded_cogs.items():
            name = lcogsv.__name__
            if cog in name.lower():
                targeted_cog = name

        try:
            logger = logging.getLogger(targeted_cog)
            self.bot.unload_extension(cog)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def reload_cog(self, ctx, *, cog: str):
        """Command which Reloads a Module.
        Remember to use dot path. e.g: cogs.owner"""
        loaded_cogs = self.bot.cogs
        if not cog.startswith('cogs.'):
            cog = "cogs." + cog

        targeted_cog = None
        for lcogs,lcogsv in loaded_cogs.items():
            name = lcogsv.__name__
            if cog in name.lower():
                targeted_cog = name
        try:
            logger = logging.getLogger(targeted_cog)
            self.bot.unload_extension(cog)
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
            self.bot.load_extension(cog)
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send('**`SUCCESS`**')

    @commands.command(aliases=['quit'], hidden=True)
    @commands.is_owner()
    async def shutdown(self, ctx):
        """Command to shutdown the bot."""
        await ctx.send('**:ok:** (Shutdown received) Bye!')
        await self.bot.logout()
        sys.exit(0)

    # @commands.command(hidden=True)
    # @commands.is_owner()
    # async def restart(self, ctx):
    #     """Command to restart the bot."""
    #     await ctx.send('**:ok:** (Restart received) BRB!')
    #     await self.bot.restart()

    @commands.command(hidden=True)
    @commands.is_owner()
    async def ignore(self, ctx, *, member: discord.Member=None):
        """Command to ignore a user."""
        await ctx.send('**:ok:** (Ignoring **`{}`** ||jk||)'.format(member.display_name))


def setup(bot):
    bot.add_cog(OwnerCog(bot))