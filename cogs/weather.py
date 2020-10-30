# import discord
from discord.ext import commands
import os
import logging
# import typing
# import pendulum
# import random
import coloredlogs
# import feedparser
import aiohttp
import redis
import pickle
from urllib.parse import quote_plus
from statistics import fmean
# from bs4 import BeautifulSoup


LOGGER = logging.getLogger(__name__)
coloredlogs.install(
    level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class WeatherCog(commands.Cog, name="Weather"):

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__
        self.aqi_key = os.environ.get("AQI_KEY")

        try:
            self.db = redis.from_url(
                os.environ.get("REDIS_URL"),
                socket_timeout=3
            )
        except Exception as e:
            LOGGER.error(e)
            pass

        try:
            _ = self.db.get('sports_db')
            self.user_db = pickle.loads(_)
        except Exception as e:
            LOGGER.debug(e)
            self.user_db = {}

    @classmethod
    def _save(self):
        _ = pickle.dumps(self.user_db)
        self.db.set('sports_db', _)

    @staticmethod
    async def fetch_json(url: str, headers=None):
        LOGGER.debug(url)
        async with aiohttp.ClientSession() as cs:
            # print(headers)
            async with cs.get(url, headers=headers) as r:
                # print(r.headers)
                return await r.json()

    @commands.command(name='aqi', aliases=['airquality'])
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def fetch_airquality(self, ctx, *, optional_input: str = None):
        """Retrieves Air Quality from PurpleAir.com"""

        member = ctx.author
        member_id = str(member.id)
        user_location = self.user_db.get(member_id, {}).get('location')

        optional_input = optional_input or user_location
        if not optional_input:
            await ctx.send("I need a place to lookup!")
            return

        purple_lookup_url = (
            "https://api.mapbox.com/geocoding/v5/mapbox.places/{query}.json?"
            "limit=14&language=en-US&access_token={key}"
        )
        purple_lookup_headers = {
            'Host': 'api.mapbox.com',
            'Connection': 'keep-alive',
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Chrome/86.0.4240.111 Safari/537.36'
            ),
            'Accept': '*/*',
            'Origin': 'https://www.purpleair.com',
            'Sec-Fetch-Site': 'cross-site',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Dest': 'empty',
            'Referer': 'https://www.purpleair.com/',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        lookup_data = await self.fetch_json(
            url=purple_lookup_url.format(
                query=quote_plus(optional_input),
                key=self.aqi_key
            ),
            headers=purple_lookup_headers
        )

        place_data = lookup_data.get("features")
        if not place_data:
            await ctx.send("I couldn't find any place by that query")
            return
        place = place_data[0].get("place_name")
        place_data = place_data[0].get("bbox")
        # SW lng, lat     NE lng, lat
        nwlat = place_data[3]
        selat = place_data[1]
        nwlng = place_data[0]
        selng = place_data[2]

        purple_api_url = (
            "https://www.purpleair.com/data.json?opt=1/m/i/mAQI/a0/cC0"
            "&fetch=true&nwlat={nwlat}&selat={selat}&nwlng={nwlng}"
            "&selng={selng}&fields=pm_0,"
        ).format(nwlat=nwlat, selat=selat, nwlng=nwlng, selng=selng)

        # LOGGER.info(purple_api_url)

        purple_data = await self.fetch_json(
            url=purple_api_url
        )

        # LOGGER.info(purple_data)

        if not purple_data.get("data"):
            await ctx.send("I couldn't find any data for that location!")
            return

        to_average = []
        for station in purple_data["data"]:
            if station[3] >= 50:
                to_average.append(station[2])

        aqi_average = fmean(to_average)

        if 0 < aqi_average <= 50:
            aqi_reply = "🟢 Good: {:.2g}".format(aqi_average)
            aqi_reply += (
                "\nAir quality is satisfactory, and air pollution poses little"
                " or no risk."
            )
        elif 50 < aqi_average <= 100:
            aqi_reply = "🟡 Moderate: {:.2g}".format(aqi_average)
            aqi_reply += (
                "\nAir quality is acceptable. However, there may be a risk for"
                " some people, particularly those who are unusually sensitive "
                "to air pollution."
            )
        elif 100 < aqi_average <= 150:
            aqi_reply = "🟠 Unhealthy for Sensitive Groups: {:.2g}".format(
                aqi_average)
            aqi_reply += (
                "\nMembers of sensitive groups may experience health effects. "
                "The general public is less likely to be affected."
            )
        elif 150 < aqi_average <= 200:
            aqi_reply = "🔴 **Unhealthy: {:.2g}**".format(aqi_average)
            aqi_reply += (
                "\nSome members of the general public may experience health "
                "effects; members of sensitive groups may experience more "
                "serious health effects."
            )
        elif 200 < aqi_average <= 300:
            aqi_reply = "🟣 **Very Unhealthy: {:.2g}**".format(aqi_average)
            aqi_reply += (
                "\nHealth alert: The risk of health effects is increased for "
                "everyone."
            )
        elif 300 < aqi_average:
            aqi_reply = "🟤 **Hazardous: {:.2g}**".format(aqi_average)
            aqi_reply += (
                "\nHealth warning of emergency conditions: everyone is more "
                "likely to be affected."
            )
        else:
            aqi_reply = "I couldn't parse that location's AQI"

        reply = "**Current AQI for {}**\n{}".format(
            place,
            aqi_reply
        )

        # LOGGER.info(purple_data)

        await ctx.send(reply)

        # embed = discord.Embed(
        #     title = combo,
        #     colour = 0x101921,
        #     description = post,
        #     url = latest.link
        # )

        # embed.set_thumbnail(url=post_image)

        # await ctx.send(content=f"**{raw_feed.feed.title}**", embed=embed)

        if user_location:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['location'] = user_location
            self._save()

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
    bot.add_cog(WeatherCog(bot))
