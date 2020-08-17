import discord
from discord.ext import commands
import sys
import logging
import typing
import pendulum


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

    @commands.command(name='seen', aliases=['last'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def seen_member(self, ctx,
                              member: typing.Optional[discord.Member] = None):
        """Tries to find the last/most recent message from a user
        e.g. seen @ra
        """

        if not member:
            await ctx.send("I need someone to look for!")
            return

        message = await ctx.send("Hang on, I'm searching this channel's chat history (this takes a second)")
        msg = await ctx.channel.history(limit=None).get(author=member)
        if not msg:
            await ctx.send("I couldn't find a recent message from {}".format(
                self._mono(member.display_name)
            ))
            return
        await message.edit(content="I last saw {} in here {} saying: \n{}".format(
            self._mono(member.display_name), 
            pendulum.parse(str(msg.created_at), strict=False).diff_for_humans(),
            self._quote(msg.clean_content)))


    def _strikethrough(self, text):
        return "~~{}~~".format(text)

    def _bold(self, text):
        return "**{}**".format(text)

    def _italics(self, text):
        return "*{}*".format(text)

    def _quote(self, text):
        return "> {}".format(text)

    def _mono(self, text):
        return "`{}`".format(text)

    def _code(self, text, lang=""):
        return "```{}\n{}\n```".format(lang, text)

    def _spoiler(self, text):
        return "||{}||".format(text)


def setup(bot):
    bot.add_cog(MiscCog(bot))