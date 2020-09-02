import discord
from discord.ext import commands
import sys
import logging
import typing
import pendulum
import random
import feedparser
import aiohttp
import textwrap
from bs4 import BeautifulSoup


class MiscCog(commands.Cog, name="Miscellaneous"):

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__
    

    @commands.command(name='albert')
    async def fetch_latest_albert(self, ctx):
        """Retrieves latest Albert post from LiveJournal"""
        url = "https://albert71292.livejournal.com/data/rss"
        raw_feed = feedparser.parse(url)
        async with aiohttp.ClientSession() as session:
            async with session.get(url.replace("/data/rss", "")) as r:
                if r.status == 200:
                    html = await r.text()
        raw_html = BeautifulSoup(html, "lxml")
        try:
            post_image = raw_html.find('div', class_='entry-userpic').find('img').get('src')
        except:
            post_image = raw_feed.feed.image.href
        latest = raw_feed.entries[0]
        post = latest.description.replace("<br />", "\n").replace("<p />", "\n")
        post = BeautifulSoup(post, "lxml").text
        post_extra = textwrap.wrap(post, width=2048, replace_whitespace=False, drop_whitespace=False)

        combo = f"{latest.title} - {pendulum.parse(latest.published, strict=False).format('MMM Do, YYYY')}"

        pages = len(post_extra)
        cur_page = 1
        embed = discord.Embed(
            title = combo,
            colour = 0x101921,
            description = post_extra[cur_page - 1],
            url = latest.link
        )

        embed.set_thumbnail(url=post_image)

        embed.set_footer(f"Page {cur_page}/{pages}")

        # await ctx.send(content=f"**{raw_feed.feed.title}**", embed=embed)
        message = await ctx.send(content=f"**{raw_feed.feed.title}**", embed=embed)
        # await ctx.send(f"Page {cur_page}/{pages}:\n{contents[cur_page-1]}")
        # getting the message object for editing and reacting

        await message.add_reaction("◀️")
        await message.add_reaction("▶️")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["◀️", "▶️"]
            # This makes sure nobody except the command sender can interact with the "menu"

        while True:
            try:
                reaction, user = await bot.wait_for("reaction_add", timeout=60, check=check)
                # waiting for a reaction to be added - times out after x seconds, 60 in this
                # example

                if str(reaction.emoji) == "▶️" and cur_page != pages:
                    cur_page += 1
                    embed.set_description(post_extra[cur_page - 1])
                    embed.set_footer(f"Page {cur_page}/{pages}")
                    await message.edit(embed=embed)
                    await message.remove_reaction(reaction, user)

                elif str(reaction.emoji) == "◀️" and cur_page > 1:
                    cur_page -= 1
                    embed.set_description(post_extra[cur_page - 1])
                    embed.set_footer(f"Page {cur_page}/{pages}")
                    await message.edit(embed=embed)
                    await message.remove_reaction(reaction, user)

                else:
                    await message.remove_reaction(reaction, user)
                    # removes reactions if the user tries to go forward on the last page or
                    # backwards on the first page
            except asyncio.TimeoutError:
                await message.remove_reaction("◀️")
                await message.remove_reaction("▶️")
                # await message.delete()
                break
                # ending the loop if user doesn't react after x seconds


        # if post_extra:
        #     embed = discord.Embed(
        #         title = "Continued...",
        #         colour = 0x101921,
        #         description = post_extra[0],
        #         url = latest.link
        #     )

        #     embed.set_thumbnail(url=post_image)

        #     await ctx.send(content=f"**{raw_feed.feed.title}**", embed=embed)


    @commands.command(name='pick', aliases=['choose', 'random', 'choice'])
    async def pick_something_randomly(self, ctx, *, optional_input: str=None):
        """Command to pick something from user input at random"""

        if not optional_input:
            return await ctx.send("I need something to choose from")
        if "," not in optional_input:
            if " or " in optional_input.lower():
                optional_input = optional_input.split(" or ")
            else:
                optional_input = optional_input.split()
        else:
            optional_input = optional_input.split(",")
        if len(optional_input) == 1:
            return await ctx.send("What do you expect from me?")
        elif len(optional_input) >= 10:
            return await ctx.send("Way too many things to choose from, try thinking for yourself!")
        choice = random.choice(optional_input)
        return await ctx.send("{}".format(self._bold(choice.strip())))

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
            await message.edit(content="I couldn't find a recent message from {}".format(
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