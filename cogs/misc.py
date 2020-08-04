import discord
from discord.ext import commands
import sys
import logging


class MiscCog(commands.Cog, name="Miscellaneous"):

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__
    

    @commands.command(name='source', aliases=['mysource', 'botsource'])
    async def show_source(self, ctx):
        """Command which shows my source code repository link."""

        embed = discord.Embed(title='My Source Code on GitHub',
                              description='@cottongin maintains me',
                              colour=0xFEFEFE,
                              url="https://github.com/cottongin/coolchat-discord-bot")

        embed.set_thumbnail(url="https://avatars2.githubusercontent.com/u/782294?s=460&v=4")
        embed.set_footer(text="https://github.com/cottongin/coolchat-discord-bot")

        await ctx.send(embed=embed)


def setup(bot):
    bot.add_cog(MiscCog(bot))