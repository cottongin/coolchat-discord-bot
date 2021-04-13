# coding=utf-8
from __future__ import absolute_import, division, print_function, unicode_literals

import logging
import shlex

import aiohttp
import coloredlogs
import pendulum
import requests

import discord
from discord.ext import commands, tasks
from discord.utils import get


LOGGER = logging.getLogger(__name__)
coloredlogs.install(
    level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class ScoresCog(commands.Cog, name="Scores"):
    """Scores Plugin featuring various scores-related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__
        self.max_check = 5 * 60

        self.base_mlb_url = (
            "https://bdfed.stitch.mlbinfra.com/bdfed/transform-mlb-scoreboard"
            "?stitch_env=prod"
            "&sortTemplate=4"
            "&sportId=1"
            "&startDate={date}&endDate={date}"
            "&gameType=E"
            "&&gameType=S"
            "&&gameType=R"
            "&&gameType=F"
            "&&gameType=D"
            "&&gameType=L"
            "&&gameType=W"
            "&&gameType=A"
            "&language=en"
            "&leagueId=104"
            "&&leagueId=103"
            "&contextTeamId="
        )

        self.date = pendulum.today()
        self.api_date = self.date.format("YYYY-MM-DD")

        self.mlb_json = self.fetch_json_requests(self.base_mlb_url.format(
            date=self.api_date
        ))

        self.states = {
            'live': ['isLive', 'isWarmup'],
            'ppd': ['isCancelled', 'isPostponed', 'isSuspended'],
            'delay': ['isDelayed', 'isInGameDelay'],
            'final': ['isFinal'],
        }

        self.monitored = {}
        self.mlb_games = {}
        self.games_start = []
        self.games_end = []
        self.games_ppd = []
        self.dupes = []
        self._parse_mlb_json_into_gameIDs()

        self._check_date.start()
        self._check_games.start()


    def cog_unload(self):
        try:
            del self.monitored
            del self.mlb_games
            del self.mlb_json
            del self.games_start
            del self.games_end
            del self.games_ppd
            del self.dupes
        except Exception as err:
            LOGGER.error(err)
            pass
        self._check_date.cancel()
        self._check_games.cancel()


    def _get_emoji(self, guild_query, emoji_query, mode=None):
        emoji_name = f"{guild_query.lower()}_{emoji_query.lower()}"
        guild = get(self.bot.guilds, name=guild_query.lower())
        if not guild:
            return ""
        emoji = get(guild.emojis, name=emoji_name)
        if not emoji:
            return ""
        if mode == "url":
            emoji = emoji.url
        else:
            emoji = "{} ".format(emoji)
        return emoji


    def _parse_mlb_json_into_gameIDs(self):
        if not self.mlb_json:
            return
        for game in self.mlb_json['dates'][0]['games']:

            def _states(state):
                return [game['gameUtils'].get(key) for key in self.states[state]]

            gid = str(game['gamePk'])

            if any(_states('live')) and not any(_states('ppd')):
                if not self.mlb_games.get(gid):
                    self.mlb_games[gid] = {'check': True}
                    self.games_start.append(gid)
                else:
                    self.mlb_games[gid]['check'] = True
                # if not self.mlb_games[gid].get('full_json'):
                self.mlb_games[gid]['full_json'] = self.fetch_json_requests(
                    f"https://statsapi.mlb.com/api/v1.1/game/{gid}/feed/live"
                )
            elif any(_states('ppd')) and not any(_states('delay')):
                if not self.mlb_games.get(gid):
                    # self.mlb_games[gid] = {'check': False}
                    # self.games_ppd.append(gid)
                    continue
                # else:
                #     self.mlb_games[gid]['check'] = False
                # self.mlb_games[gid]['ppd'] = True
                self.games_ppd.append(gid)
                self.mlb_games.pop(gid, None)
            elif any(_states('delay')) and not any(_states('ppd')):
                if not self.mlb_games.get(gid):
                    self.mlb_games[gid] = {'check': False}
                    # self.games_ppd.append(gid)
                else:
                    self.mlb_games[gid]['check'] = False
                self.mlb_games[gid]['delay'] = True
            elif any(_states('final')):
                self.mlb_games.pop(gid, None)
                self.games_end.append(gid)
            else:
                for stale_game in self.mlb_games:
                    if str(stale_game) not in [str(x.get('gamePk')) for x in self.mlb_json['dates'][0]['games']]:
                        self.mlb_games.pop(str(stale_game), None)
                self.mlb_games.pop(gid, None)


    @tasks.loop(seconds=10)
    async def _check_games(self):
        LOGGER.info("--------------------------------------")
        # now = pendulum.now().format("DD-MMM HH:mm:ss")
        LOGGER.info(f"checking games...")
        if not self.mlb_games:
            old_interval = self._check_games.seconds
            if old_interval <= self.max_check:
                new_interval = max(10, min(old_interval + 10, self.max_check))
                self._check_games.change_interval(seconds=new_interval)
                self._check_date.change_interval(seconds=new_interval)
                LOGGER.debug("no games, back off timers [{}s -> {}s]".format(
                    old_interval,
                    new_interval,
                ))
            else:
                LOGGER.debug("no games, timers maxed out [{}s]".format(
                    self.max_check
                ))
            return
        else:
            old_interval = self._check_games.seconds
            if old_interval != 10:
                self._check_games.change_interval(seconds=10)
                self._check_date.change_interval(seconds=10)
                LOGGER.debug("new games, resetting timers [10s]")

        # check starting games
        for gid in self.games_start.copy():
            if not self.mlb_games.get(gid):
                continue
            data = self.mlb_games[gid].get('full_json')
            if not data:
                continue
            gd = data['gameData']
            away = gd['teams']['away']
            home = gd['teams']['home']
            away_lineup = []
            home_lineup = []
            away_players = data['liveData']['boxscore']['teams']['away']
            home_players = data['liveData']['boxscore']['teams']['home']
            for idx, player in enumerate(away_players['battingOrder']):
                pd = away_players['players'].get("ID{}".format(player))
                away_lineup.append("{}. {} ({})".format(
                    idx + 1,
                    pd['person']['fullName'],
                    pd['position']['abbreviation'],
                ))
            away_pitcher = gd['probablePitchers']['away']['id']
            home_pitcher = gd['probablePitchers']['home']['id']
            away_lineup.append("SP: {} ({})".format(
                away_players['players'].get(f"ID{away_pitcher}")['person']['fullName'],
                away_players['players'].get(f"ID{away_pitcher}")['seasonStats']['pitching']['era'],
            ))
            for idx, player in enumerate(home_players['battingOrder']):
                pd = home_players['players'].get("ID{}".format(player))
                home_lineup.append("{}. {} ({})".format(
                    idx + 1,
                    pd['person']['fullName'],
                    pd['position']['abbreviation'],
                ))
            home_lineup.append("SP: {} ({})".format(
                home_players['players'].get(f"ID{home_pitcher}")['person']['fullName'],
                home_players['players'].get(f"ID{home_pitcher}")['seasonStats']['pitching']['era'],
            ))
            weather = (
                "**Weather Report**\n"
                "🌡 {temp}°F\n"
                "🪟 Conditions: {condition}\n"
                "💨 Wind: {wind}"
            ).format(**gd.get('weather', {}))
            venue = (
                "**Location**\n"
                "__{name}__ {location}\n"
                "{details}"
            ).format(
                name=gd.get('venue', {}).get('name', 'UNK'),
                location="{city} {stateAbbrev}".format(**gd.get('venue', {}).get('location', {})),
                details="🏟 {capacity:,} / {roofType} / {turfType}".format(
                    **gd.get('venue', {}).get('fieldInfo', {})
                )
            )
            away_emoji = self._get_emoji('mlb', away['abbreviation'])
            home_emoji = self._get_emoji('mlb', home['abbreviation'])
            embed = discord.Embed(
                title="{}{} ({}) @ {}{} ({}) is _starting soon_".format(
                    away_emoji,
                    away['teamName'],
                    "{}-{} {}".format(
                        away.get('record', {}).get('wins', 0),
                        away.get('record', {}).get('losses', 0),
                        away.get('record', {}).get('winningPercentage', '.000'),
                    ),
                    home_emoji,
                    home['teamName'],
                    "{}-{} {}".format(
                        home.get('record', {}).get('wins', 0),
                        home.get('record', {}).get('losses', 0),
                        home.get('record', {}).get('winningPercentage', '.000'),
                    ),
                ),
                color=0x80AC5F,
                description="\n".join([weather, venue]),
            )
            embed.add_field(
                name="`{} Lineup`".format(away['abbreviation']),
                value="\n".join(away_lineup)
            )
            embed.add_field(
                name="`{} Lineup`".format(home['abbreviation']),
                value="\n".join(home_lineup)
            )
            message = (
                "{} ({}) @ {} ({}) is **starting soon**\n"
                "{} Lineup: {}\n"
                "{} Lineup: {}"
            ).format(
                away['teamName'],
                "{}-{} {}".format(
                    away.get('record', {}).get('wins', 0),
                    away.get('record', {}).get('losses', 0),
                    away.get('record', {}).get('winningPercentage', '.000'),
                ),
                home['teamName'],
                "{}-{} {}".format(
                    home.get('record', {}).get('wins', 0),
                    home.get('record', {}).get('losses', 0),
                    home.get('record', {}).get('winningPercentage', '.000'),
                ),
                away['abbreviation'], " ".join(away_lineup),
                home['abbreviation'], " ".join(home_lineup),
            )
            msg_hash = hash(gid + message)
            if msg_hash not in self.dupes:
                for channel in self.monitored:
                    await channel.send(embed=embed)
                self.dupes.append(msg_hash)
            self.games_start.remove(gid)

        # check ending games
        for gid in self.games_end.copy():
            if not self.mlb_games.get(gid):
                continue
            data = self.mlb_games[gid].get('full_json')
            if not data:
                continue
            message = " is ending"
            # SD 2 [H5 E0 LOB6] @ TEX 0 [H5 E0 LOB10] is final! 9/F (W: Craig Stammen (4.05/1-1) L: Mike Foltynewicz (4.09/0-2) S: Mark Melancon (0.00/5-0))
            away_team = data['gameData']['teams']['away']['teamName']
            away_score = data['liveData']['linescore']['teams']['away']['runs']
            home_team = data['gameData']['teams']['home']['teamName']
            home_score = data['liveData']['linescore']['teams']['home']['runs']
            inning = data['liveData']['linescore']['currentInning']
            away_emoji = self._get_emoji('mlb', data['gameData']['teams']['away']['abbreviation'])
            home_emoji = self._get_emoji('mlb', data['gameData']['teams']['home']['abbreviation'])
            if away_score > home_score:
                away_team = f"**{away_team}"
                away_score = f"{away_score}**"
            elif home_score > away_score:
                home_team = f"**{home_team}"
                home_score = f"{home_score}**"
            embed = discord.Embed(
                description="{}{} {} @ {}{} {} is final! {}/F".format(
                    away_emoji,
                    away_team,
                    away_score,
                    home_emoji,
                    home_team,
                    home_score,
                    inning
                ),
                color=0xD0021B
            )
            msg_hash = hash(gid + message)
            if msg_hash not in self.dupes:
                for channel in self.monitored:
                    await channel.send(embed=embed)
                self.dupes.append(msg_hash)
            self.games_end.remove(gid)

        # check ongoing games
        for gid, game in self.mlb_games.copy().items():
            if not self.mlb_games.get(gid):
                continue
            if not self.mlb_games[gid].get('check'):
                continue
            LOGGER.debug(f"fetching json for {gid}")
            new_json = await self.fetch_json(
                f"http://statsapi.mlb.com/api/v1/game/{gid}/playByPlay"
            )
            self.mlb_games[gid]['new_json'] = new_json
            if not game.get('old_json'):
                self.mlb_games[gid]['old_json'] = new_json.copy()

        for gid, game in self.mlb_games.copy().items():
            if not self.mlb_games.get(gid):
                continue
            if not game.get('check'):
                continue

            old_plays = game['old_json']['scoringPlays']
            new_plays = game['new_json']['scoringPlays']
            swap = False
            if old_plays == new_plays:
                swap = False
                continue
            else:
                swap = True
                # LOGGER.debug(old_plays)
                # LOGGER.debug(new_plays)
                # LOGGER.debug(old_plays + new_plays)
                all_plays = old_plays + new_plays
                scoring_plays = [play for play in all_plays if all_plays.count(play)==1]
                LOGGER.debug(scoring_plays)
                # scoring_plays = set(old_plays + new_plays)

            for idx in scoring_plays:
                scoring_play = game['new_json']['allPlays'][idx]
                # details = None
                # for gd in self.mlb_json['dates'][0]['games'].copy():
                #     if int(gd['gamePk']) == int(gid):
                #         details = gd
                #         LOGGER.debug((
                #             "{}\t[{}] found details ... "
                #             "mlb_json['{}'] ... {}").format(
                #                 now,
                #                 gid,
                #                 gd['gamePk'],
                #                 (int(gd['gamePk']) == int(gid)),
                #             ))
                #         break
                details = game.get('full_json', {}).get('gameData', {})
                halfInning = {
                    'bottom': '⬇',
                    'top': '⬆',
                }
                homer = False
                event = ""
                if scoring_play['result'].get('event'):
                    event = "{} · ".format(scoring_play['result']['event'].upper())
                    homer = True if scoring_play['result']['eventType'] == "home_run" else False
                if homer:
                    hit_details = ""
                    for play in scoring_play['playEvents']:
                        if play.get('hitData'):
                            hit_details = "**{launchSpeed} mph** · ∡{launchAngle}° · **{totalDistance} ft**".format(
                                **play['hitData']
                            )
                            break
                else:
                    hit_details = ""
                message = "{} {} - {}{}{}".format(
                    halfInning.get(scoring_play['about']['halfInning']),
                    self.make_ordinal(scoring_play['about']['inning']),
                    event,
                    scoring_play['result']['description'],
                    hit_details,
                )
                away_emoji = self._get_emoji('mlb', details['teams']['away']['abbreviation'])
                home_emoji = self._get_emoji('mlb', details['teams']['home']['abbreviation'])
                scoring_team = ""
                scoring_team_emoji_url = ""
                if details:
                    if scoring_play['about']['halfInning'] == "bottom":
                        home_tag = "**"
                        away_tag = ""
                        scoring_team = "{} · ".format(details['teams']['home']['abbreviation'])
                        scoring_team_emoji_url = self._get_emoji('mlb', details['teams']['home']['abbreviation'], 'url')
                        away_or_home = "away"
                    else:
                        home_tag = ""
                        away_tag = "**"
                        scoring_team = "{} · ".format(details['teams']['away']['abbreviation'])
                        scoring_team_emoji_url = self._get_emoji('mlb', details['teams']['away']['abbreviation'], 'url')
                        away_or_home = "home"
                    linescore = game.get('full_json', {}) \
                                    .get('liveData', {}) \
                                    .get('linescore', {})
                    message = "{}{} {}{} @ {}{} {}{} - {}".format(
                        away_tag,
                        details['teams']['away']['abbreviation'],
                        # linescore['teams']['away']['runs'],
                        scoring_play['result'].get('awayScore', 0),
                        away_tag,
                        home_tag,
                        details['teams']['home']['abbreviation'],
                        # linescore['teams']['home']['runs'],
                        scoring_play['result'].get('homeScore', 0),
                        home_tag,
                        message,
                    )
                scoring_player = [scoring_play['matchup']['batter']['id'], scoring_play['matchup']['batter']['fullName']]
                pitcher_id = "ID{}".format(scoring_play['matchup']['pitcher']['id'])
                # t = game.get('full_json')
                # t = t.get('liveData')
                # t = t.get('boxscore')
                # t = t.get('teams')
                # t = t.get(away_or_home)
                # t = t.get('players')
                # print(t, pitcher_id)
                # t = t.get(pitcher_id)
                # t = t.get('stats')
                # t = t.get('pitching')
                # t = t.get('numberOfPitches', 0)
                # print(t)
                num_pitches = game.get(
                    'full_json', {}).get(
                        'liveData', {}).get(
                            'boxscore', {}).get(
                                'teams', {}).get(
                                    away_or_home, {}).get(
                                        'players', {}).get(
                                            pitcher_id, {}).get(
                                                'stats', {}).get(
                                                    'pitching', {}).get(
                                                        'numberOfPitches', 0)
                pitcher = "{}{}".format(
                    scoring_play['matchup']['pitcher']['fullName'],
                    " (pitch #{})".format(
                        num_pitches
                    ),
                )
                line = "{0}{8}{1} {2}{0} @ {3}{9}{4} {5}{3} {6} {7}".format(
                    away_tag,
                    details['teams']['away']['abbreviation'],
                    scoring_play['result'].get('awayScore', 0),
                    home_tag,
                    details['teams']['home']['abbreviation'],
                    scoring_play['result'].get('homeScore', 0),
                    halfInning.get(scoring_play['about']['halfInning']),
                    self.make_ordinal(scoring_play['about']['inning']),
                    away_emoji,
                    home_emoji
                )
                embed = discord.Embed(
                    description="{}\n{}".format(
                        line,
                        scoring_play['result']['description'],
                    ),
                    color=0xFFFFFF,
                    # timestamp=pendulum.now(),
                )
                embed.set_thumbnail(
                    url=scoring_team_emoji_url
                )
                embed.set_author(
                    name="{play_type}{team}{player}".format(
                        play_type=event,
                        team=scoring_team,
                        player=scoring_player[1]
                    ),
                    icon_url="https://img.mlbstatic.com/mlb-photos/image/upload/w_124,q_auto:best/v1/people/{player_id}/headshot/83/current".format(
                        player_id=scoring_player[0]
                    )
                )
                embed.add_field(
                    name="`vs`",
                    value=pitcher,
                    inline=True
                )
                # embed_json = {
                #     "embed": {
                #         # "title": "{0}{1} {2}{0} @ {3}{4} {5}{3} {6} {7}".format(
                #         #     away_tag,
                #         #     details['teams']['away']['abbreviation'],
                #         #     scoring_play['result'].get('awayScore', 0),
                #         #     home_tag,
                #         #     details['teams']['home']['abbreviation'],
                #         #     scoring_play['result'].get('homeScore', 0),
                #         #     halfInning.get(scoring_play['about']['halfInning']),
                #         #     self.make_ordinal(scoring_play['about']['inning']),
                #         # ),
                #         # "description": scoring_play['result']['description'],
                #         # "color": 13632027,
                #         # "timestamp": pendulum.now().to_iso8601_string,
                #         # "thumbnail": {
                #         #     "url": "https://img.mlbstatic.com/mlb-photos/image/upload/w_124,q_auto:best/v1/people/{player_id}/headshot/83/current".format(
                #         #         player_id=scoring_player[0]
                #         #     )
                #         # },
                #         # "author": {
                #         #     # "name": "{play_type}{team}{player}".format(
                #         #     #     play_type=event,
                #         #     #     team=scoring_team,
                #         #     #     player=scoring_player[1]
                #         #     # )
                #         # },
                #         "fields": [
                #             {
                #                 "name": "`vs`",
                #                 "value": pitcher,
                #                 "inline": True
                #             }
                #         ]
                #     }
                # }
                if homer:
                    embed.add_field(
                        name="`StatCast`",
                        value=hit_details,
                        inline=True
                    )
                # LOGGER.debug(embed_json)
                # embed = discord.Embed.from_dict(embed_json)
                msg_hash = hash(gid + message)
                if msg_hash not in self.dupes:
                    for channel in self.monitored:
                        await channel.send(embed=embed)
                    self.dupes.append(msg_hash)
            del scoring_plays
            if swap:
                self.mlb_games[gid]['old_json'] = game['new_json']
            # self.mlb_games[gid] = game


    @tasks.loop(seconds=10)
    async def _check_date(self):
        now = pendulum.now()
        if pendulum.today() != self.date:
            LOGGER.info("Day Change Detected\nSwapping...")
            LOGGER.debug("{} {}".format(self.api_date, self.date))
            self.date = pendulum.today()
            self.api_date = pendulum.today().format("YYYY-MM-DD")
            LOGGER.debug("{} {}".format(self.api_date, self.date))
        LOGGER.info(
            "fetching main json - {}".format(
                self.base_mlb_url.format(date=self.api_date)
            )
        )
        self.mlb_json = self.fetch_json_requests(
            self.base_mlb_url.format(
                date=self.api_date
            )
        )
        self._parse_mlb_json_into_gameIDs()


    # @commands.command(name='testlist')
    # async def testlist(self, ctx):
    #     for key, value in self.monitored.items():
    #         await value.send(f"{value}")
    #         message = ""
    #         for key_, value_ in self.mlb_games.items():
    #             message += str(value_) + ", " + str(key_) + "\n"
            
    #         await value.send(message)


    @commands.command(name='start', aliases=['startscores'])
    @commands.is_owner()
    async def start_mlb_scores(self, ctx, *, optional_input: str = None):
        """Start emitting MLB live scores in the channel this command is sent
        from
        """

        if not self.mlb_json:
            return

        if ctx.channel not in self.monitored:
            self.monitored[ctx.channel] = ctx.channel
            await ctx.send(f"Added `{ctx.channel}` to my announce list")
        else:
            await ctx.send(f"`{ctx.channel}` is already on my announce list")


    @commands.command(name='stop', aliases=['stopscores'])
    @commands.is_owner()
    async def stop_mlb_scores(self, ctx):
        """Stop emitting MLB live scores in the channel this command is sent
        from
        """
        if ctx.channel in self.monitored:
            self.monitored.pop(ctx.channel, None)
            await ctx.send(f"Removed `{ctx.channel}` from my announce list")
        else:
            await ctx.send(f"`{ctx.channel}` isn't on my announce list")


    @commands.command(name='timers', aliases=['t'])
    @commands.is_owner()
    async def control_timers(self, ctx, *, optional_input: str = ""):
        """Control all timed loops for MLB live scoring"""

        if optional_input.lower() == "start":
            self._check_date.start()
            self._check_games.start()
            await ctx.send("All timers started")
            return
        elif optional_input.lower() == "stop":
            self._check_date.stop()
            self._check_games.stop()
            await ctx.send("All timers stopped")
            return
        elif optional_input.lower() == "cancel":
            self._check_date.cancel()
            self._check_games.cancel()
            await ctx.send("All timers canceled")
            return
        elif optional_input.lower() == "restart":
            self._check_date.cancel()
            self._check_games.cancel()
            self._check_date.start()
            self._check_games.start()
            await ctx.send("All timers restarted")
            return
        else:
            await ctx.send("What exactly would you like me to do with the timers...")
            return


#############
## Helpers ##
#############


    @staticmethod
    async def fetch_json(url: str):
        async with aiohttp.ClientSession() as cs:
            async with cs.get(url) as r:
                return await r.json()


    @staticmethod
    def fetch_json_requests(url: str):
        try:
            response = requests.get(url).json()
            return response
        except:
            return


    # from https://stackoverflow.com/a/50992575/14790347
    @staticmethod
    def make_ordinal(n):
        '''
        Convert an integer into its ordinal representation::

            make_ordinal(0)   => '0th'
            make_ordinal(3)   => '3rd'
            make_ordinal(122) => '122nd'
            make_ordinal(213) => '213th'
        '''
        n = int(n)
        suffix = ['th', 'st', 'nd', 'rd', 'th'][min(n % 10, 4)]
        if 11 <= (n % 100) <= 13:
            suffix = 'th'
        return str(n) + suffix


    @classmethod
    def _parseargs(self, passed_args):
        if passed_args:
            args = shlex.split(passed_args)

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


    def _parse_optinput(self, ctx, optional_input):
        date = pendulum.now()
        append_team = ""
        timezone = ""
        args_dev = self._parseargs(optional_input)
        if args_dev.get('--tz'):
            # grab the user-defined timezone
            timezone = args_dev.get('--tz')
            # see if it's a short-hand timezone first
            timezone = self.short_tzs.get(timezone.lower()) or timezone
            # now check if it's valid
            try:
                _ = pendulum.timezone(timezone)
            except Exception:
                return
        if args_dev.get('extra_text', '').lower() == "yesterday":
            date = pendulum.yesterday().in_tz(
                user_timezone or self.default_other_tz)
        elif args_dev.get('extra_text', '').lower() == "tomorrow":
            date = pendulum.tomorrow().in_tz(
                user_timezone or self.default_other_tz)
        else:
            try:
                date = pendulum.parse(
                    args_dev.get('extra_text'), 
                    strict=False
                )
            except:
                append_team = args_dev.get('extra_text').lower()
        
        return date, append_team, timezone, args_dev

    async def _build_embed(self, data, mobile=False, color=0x98FB98):
        pass


def setup(bot):
    bot.add_cog(ScoresCog(bot))
