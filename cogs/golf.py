import discord
from discord.ext import commands
from discord.utils import get

import requests
import pendulum
import aiohttp
from tempfile import mkstemp
import subprocess
import logging
import coloredlogs
import random
import os
import time
import redis
import shlex
import pickle


LOGGER = logging.getLogger(__name__)
coloredlogs.install(
    level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class GolfCog(commands.Cog, name="Golf"):
    """Golf Plugin featuring various golf-related commands"""

    def __init__(self, bot):
        self._debug = True
        self.bot = bot
        self.__name__ = __name__
        try:
            self.db = redis.from_url(
                os.environ.get("REDIS_URL"),
                socket_timeout=3
            )
        except Exception as e:
            LOGGER.error(e)
            pass

        self.default_tz = "US/Eastern"
        # ^ If a user doesn't provide a tz what should we use?
        self.default_now_tz = "US/Pacific"
        # ^ When looking for "today's" games we want to look at the last tz
        # to switch days
        self.default_other_tz = "US/Pacific"
        # ^ When looking ahead or behind "today's" games we want to look at the
        # first tz to switch days... I think. Hence why this is set separately
        # from self.default_tz
        # update: turns out i'm wrong here. think we actually want this to be
        # the same as default_now_tz

        self.short_tzs = {
            "edt": "US/Eastern",
            "est": "US/Eastern",
            "cdt": "US/Central",
            "cst": "US/Central",
            "mst": "US/Mountain",
            "mdt": "US/Mountain",
            "pst": "US/Pacific",
            "pdt": "US/Pacific"
        }

        try:
            _ = self.db.get('sports_db')
            self.user_db = pickle.loads(_)
        except Exception as e:
            LOGGER.debug(e)
            self.user_db = {}

        self.PGA_ID = (
            "exp=1617984833~"
            "acl=*~"
            "hmac=88ca1002f684dec0b53927d45d49f3f82e0438f5379a70c1e63071b2c0930ce9"
        )

        self.PGA_API_URLs = {
            "schedule": (
                "https://statdata.pgatour.com/r/current/schedule-v2.json"
            ),
            "leaderboard": (
                "https://statdata.pgatour.com/{tour_type}/{tour_id}/"
                "leaderboard-v2mini.json?userTrackingId={pgacom_id}"
            ),
            "current": (
                "https://statdata.pgatour.com/r/current/message.json"
            ),
        }

    @classmethod
    def _fetch_pgacom_id(self):
        """pgatour.com sigh"""
        # based on https://gist.github.com/thayton/a5d0c4319d9657d1816fa94ff62e0452

        url = "https://microservice.pgatour.com/js"
        resp = requests.get(url)
        text = "window = {{}}; {}; console.log(window.pgatour.setTrackingUserId('id8730931'));".format(resp.text)

        fd, path = mkstemp()

        with os.fdopen(fd, "w") as fp:
            fp.write(text)

        userid = subprocess.check_output(["node", path]).strip()
        userid = ''.join(chr(c) for c in userid) # convert to str
        
        os.unlink(path)

        # Create the URL directly as requests will percent encode the userid
        # value causing a 403 from the server... 
        # url = '{0}?userTrackingId={1}'.format(self.url, userid)
        return userid


    @classmethod
    def _parseargs(self, passed_args):
        if passed_args:
            # passed_args = passed_args.replace("'", '')
            args = shlex.split(passed_args)
            # options = {}

            options = {
                k: True if v.startswith('-') else v
                for k,v in zip(args, args[1:]+["--"]) if k.startswith('-')
            }

            extra = args
            if options:
                extra = []
                for k,v in options.items():
                    for arg in args:
                        if arg != k and arg != v:
                            extra.append(arg)

            options['extra_text'] = ' '.join(extra)
            return options
        else:
            return {}

    @staticmethod
    async def fetch_json(url: str):
        async with aiohttp.ClientSession() as cs:
            async with cs.get(url) as r:
                return await r.json()

    @commands.command(name='golf', aliases=["pga"])
    async def do_golf_scores(self, ctx, *, optional_input: str = None):
        """Fetches golf leaderboard for current tournament if any
        """
        emit = ctx.send
        embed_color = 0x003e7e
        response = await self.fetch_json(self.PGA_API_URLs['current'])
        userid = self._fetch_pgacom_id()
        url = self.PGA_API_URLs['leaderboard'].format(
            tour_type=response.get('tc', 'r'),
            tour_id=response.get('tid', '404'),
            pgacom_id=userid
        )

        if self._debug:
            await emit(f"[DEBUG] {url}")

        response = await self.fetch_json(url)
        if not response.get('leaderboard'):
            await emit("Sorry, couldn't find a leaderboard")
            return

        leaderboard = response.get('leaderboard', {})
        embed = discord.Embed(
            title="Top 10",
            color=embed_color,
        )
        embed.set_author(
                name='PGA Leaderboard for "{tourney}" ({start} - {end})'.format(
                    tourney=leaderboard.get('tournament_name', 'UNK'),
                    start=pendulum.parse(leaderboard.get('start_date'), strict=False).format("MMM Do"),
                    end=pendulum.parse(leaderboard.get('end_date'), strict=False).format("MMM Do"),
                ),
                url=f"https://pgatour.com",
                icon_url="https://upload.wikimedia.org/wikipedia/en/thumb/7/77/PGA_Tour_logo.svg/188px-PGA_Tour_logo.svg.png"
            )
        top5 = leaderboard.get('players', [])[:10]
        content = ""
        for player in top5:
            details = ""
            if player.get('thru'):
                details = "_ thru {} ({})_"
            else:
                for rnd in player['rounds']:
                    if rnd['round_number'] == player['current_round']:
                        details = " ({})".format(pendulum.parse(rnd['tee_time'], tz="US/Eastern", strict=False).format("MMM Do h:mm A zz"))
                        break
            content += "[{}]  {}  | **{}**{}\n".format(
                player['current_position'],
                "{}. {}".format(player['player_bio']['short_name'], player['player_bio']['last_name']),
                player['total'],
                details.format(
                    player['thru'],
                    player['today'],
                ),
            )
        embed.description = content
        await emit(embed=embed)

def setup(bot):
    bot.add_cog(GolfCog(bot))