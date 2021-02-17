import discord
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
import pendulum
import re
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
        self.google_api_key = os.environ.get("GOOGLE_API_KEY")
        self.weather_api_key = os.environ.get("WEATHER_API_KEY")

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

    # @classmethod
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
            "&selng={selng}&fields=pm_0"
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

        if optional_input:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['location'] = optional_input
            self._save()

    @commands.command(name='weather', aliases=['w', 'wz'])
    # @commands.cooldown(1, 30, commands.BucketType.user)
    async def fetch_weather(self, ctx, *, optional_input: str = None):
        """Retrieves Weather from OpenWeatherMap"""

        member = ctx.author
        member_id = str(member.id)
        user_location = self.user_db.get(member_id, {}).get('location')

        optional_input = optional_input or user_location
        if not optional_input:
            await ctx.send("I need a place to lookup!")
            return

        lat, lon, loc = await self._get_latlon(optional_input)
        weather_data = await self._get_weather(lat, lon)
        embed = await self._build_embed(loc, weather_data)

        await ctx.send(embed=embed)

        if weather_data.get('alerts'):
            for alert in weather_data['alerts']:
                embed = await self._build_alert_embed(alert, weather_data['timezone'])
                await ctx.send(embed=embed)

        if optional_input:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['location'] = optional_input
            self._save()

    async def _build_alert_embed(self, alert, tz):
        color = 0xffae42
        title = alert['event']
        fromto = "Valid from {} to {}".format(
            pendulum.from_timestamp(alert['start']).in_tz(tz).format("ddd MMM DD HH:mm zz"),
            pendulum.from_timestamp(alert['end']).in_tz(tz).format("ddd MMM DD HH:mm zz")
        )
        # desc = "**{}**\n{}".format(fromto, alert['description']) #.replace("\n", " "))
        desc = fromto
        embed = discord.Embed(
            title="⚠️ {}".format(title),
            color=color,
            description=desc,
        )
        # embed.set(url="https://img.cottongin.xyz/i/wdusfu3s.png")
        return embed

    async def _build_embed(self, location, weather_data):
        """build embed for weather"""
        LOGGER.debug(location)
        location = "{}".format(re.sub(r'\b\d{5}\b', '', location)).strip()
        if location.endswith('USA'):
            units_mode = 'imperial'
            location = location.replace(", USA", "")
        else:
            units_mode = 'metric'
        color = 0xe96e50
        title = f"**Weather for {location}**"
        tz = weather_data['timezone']
        today = weather_data['daily'][0]
        precip2day = ""
        if today['pop']:
            amt = today.get('snow', 0) or today.get('rain', 0)
            amt = round(amt / 25.4, 1)
            if amt:
                amt = ' ({:.1f}")'.format(amt)
            else:
                amt = ""
            precip2day = "{:.0%} chance of precipitation{}\n".format(today['pop'], amt)
        desc = (
            "**__Currently:__**\n"
            "{} - _Feels Like_ {}\n"
            "{}{}\n:sunrise: `{}` :city_sunset: `{}`\n"
            "**{}%** humidity | **{}%** ☁️ | **{:0.1f}mi** visibility\n"
            "**{}** mph winds from the **{}**\n\n"
            "**__Today:__**\n"
            "{}{}\nHigh: {}\nLow: {}\n{}\n"
        ).format(
            await self._units(weather_data['current']['temp'], unit=units_mode),
            await self._units(weather_data['current']['feels_like'], unit=units_mode),
            await self._get_icon(weather_data['current']['weather'][0]['main']),
            weather_data['current']['weather'][0]['description'].title(),
            pendulum.from_timestamp(weather_data['current']['sunrise']).in_tz(tz).format("HH:mm zz"),
            pendulum.from_timestamp(weather_data['current']['sunset']).in_tz(tz).format("HH:mm zz"),
            weather_data['current']['humidity'],
            weather_data['current']['clouds'],
            round(weather_data['current']['visibility'] / 1609, 2),
            round(weather_data['current']['wind_speed']),
            await self._get_wind(weather_data['current']['wind_deg']),
            await self._get_icon(today['weather'][0]['main']),
            today['weather'][0]['description'].title(),
            await self._units(today['temp']['max'], unit=units_mode),
            await self._units(today['temp']['min'], unit=units_mode),
            precip2day,
        )
        embed = discord.Embed(
            title=title,
            colour=color,
            description=desc,
        )

        current_icon = weather_data['current']['weather'][0]['icon']
        embed.set_thumbnail(url=f"http://openweathermap.org/img/wn/{current_icon}@2x.png")

        for day in weather_data['daily'][1:4]:
            if day['pop']:
                amt = day.get('snow', 0) or day.get('rain', 0)
                amt = round(amt / 25.4, 1)
                if amt:
                    amt = ' ({:.1f}")'.format(amt)
                else:
                    amt = ""
                precip = "\n{:.0%} chance of precipitation{}\n".format(day['pop'], amt)
            else:
                precip = ""
            dayname = pendulum.from_timestamp(day['dt']).in_tz(tz).format("dddd")
            forecast = "{}{}\nHigh: {}\nLow: {}{}".format(
                await self._get_icon(day['weather'][0]['main']),
                day['weather'][0]['description'].title(),
                await self._units(day['temp']['max'], unit=units_mode),
                await self._units(day['temp']['min'], unit=units_mode),
                precip,
            )
            embed.add_field(
                name="__{}:__".format(dayname),
                value=forecast,
                inline=True
            )

        embed.set_footer(text="Powered by OpenWeatherMap", icon_url="https://openweathermap.org/themes/openweathermap/assets/vendor/owm/img/icons/logo_32x32.png")

        return embed

    async def _units(self, inp, unit='imperial', mode='temp'):
        output = inp
        if unit == 'imperial':
            if mode == 'temp':
                # (32°F − 32) × 5/9 = 0°C
                c = round((inp - 32) * 5/9, 1)
                output = "**{}°F**\u00A0({:.1f}°C)".format(round(inp), c)
        elif unit == 'metric':
            if mode == 'temp':
                # (32°F − 32) × 5/9 = 0°C
                c = round((inp - 32) * 5/9, 1)
                output = "**{:.1f}°C**\u00A0({}°F)".format(c, round(inp))
        return output

    async def _get_icon(self, desc):
        return {
            'Thunderstorm': '⛈ ',
            'Drizzle':      '🌧 ',
            'Rain':         '🌧 ',
            'Snow':         '❄️ ',
            'Mist':         '🌫 ',
            'Smoke':        '🌫 ',
            'Haze':         '🌫 ',
            'Dust':         '🌫 ',
            'Fog':          '🌫 ',
            'Sand':         '🌫 ',
            'Dust':         '🌫 ',
            'Ash':          '🌫 ',
            'Squall':       '🌫 ',
            'Tornado':      '🌪 ',
            'Clear':        '☀️ ',
            'Clouds':       '⛅️ ',
        }.get(desc, "")

    async def _get_wind(self, bearing):
        """get wind direction"""

        if (bearing <= 22.5) or (bearing > 337.5):
            bearing = 'north ⬇️'
        elif (bearing > 22.5) and (bearing <= 67.5):
            bearing = 'northeast ↙️'
        elif (bearing > 67.5) and (bearing <= 112.5):
            bearing = 'east ⬅️'
        elif (bearing > 112.5) and (bearing <= 157.5):
            bearing = 'southeast ↖️'
        elif (bearing > 157.5) and (bearing <= 202.5):
            bearing = 'south ⬆️'
        elif (bearing > 202.5) and (bearing <= 247.5):
            bearing = 'southwest ↗️'
        elif (bearing > 247.5) and (bearing <= 292.5):
            bearing = 'west ➡️'
        elif (bearing > 292.5) and (bearing <= 337.5):
            bearing = 'northwest ↘️'

        return bearing

    async def _get_weather(self, lat, lon):
        """gets weather"""
        api_key = self.weather_api_key
        url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&appid={api_key}&units=imperial"

        LOGGER.debug(url)

        response = await self.fetch_json(url=url)

        return response

    # @classmethod
    async def _get_latlon(self, user_location):
        """Gets latitude and longitude for a location"""
        url = "https://maps.googleapis.com/maps/api/geocode/json?address={user_location}&key={api_key}"
        lat = lon = loc = None

        try:
            url = url.format(user_location=user_location, api_key=self.google_api_key)
            data = await self.fetch_json(url=url)
            # LOGGER.debug(data.url)
            # data = data.json()

            data = data['results'][0]

            loc = data['formatted_address']
            lat = data['geometry']['location']['lat']
            lon = data['geometry']['location']['lng']
        except Exception as err:
            LOGGER.debug(err)

        return lat, lon, loc

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
