import discord
from discord.ext import commands
from discord.utils import get

import requests
import pendulum
import aiohttp

import logging
import coloredlogs
# import json
import random
import os
# import errno
import time
import redis
import pickle


LOGGER = logging.getLogger(__name__)
coloredlogs.install(
    level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class SportsCog(commands.Cog, name="Sports"):
    """Sports Plugin featuring various sports-related commands"""

    def __init__(self, bot):
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

        # if not os.path.exists(os.path.dirname("data/sports_db.json")):
        #     try:
        #         os.makedirs(os.path.dirname("data/sports_db.json"))
        #     except OSError as exc: # Guard against race condition
        #         if exc.errno != errno.EEXIST:
        #             raise

        # try:
        #     with open('data/sports_db.json') as f:
        #         self.user_db = json.load(f)
        # except:
        #     self.user_db = {}

        try:
            _ = self.db.get('sports_db')
            self.user_db = pickle.loads(_)
        except Exception as e:
            LOGGER.debug(e)
            self.user_db = {}

        self.NHL_SCOREBOARD_ENDPOINT = (
            "https://statsapi.web.nhl.com/api/v1/schedule?"
            "startDate={}&endDate={}"
            "&expand=schedule.teams,schedule.linescore,"
            "schedule.broadcasts.all,"
            "schedule.ticket,schedule.game.content.media.epg,"
            "schedule.game.seriesSummary"
            "&leaderCategories=&site=en_nhl&teamId=")
        self.MLB_SCOREBOARD_ENDPOINT = (
            'https://statsapi.mlb.com/api/v1/schedule'
            '?sportId=1,51&date={}'
            '&hydrate=team(leaders(showOnPreview('
            'leaderCategories=[homeRuns,runsBattedIn,'
            'battingAverage],statGroup=[pitching,'
            'hitting]))),linescore(matchup,runners),'
            'flags,liveLookin,review,broadcasts(all),'
            'decisions,person,probablePitcher,stats,'
            'homeRuns,previousPlay,game(content('
            'media(featured,epg),summary),tickets),'
            'seriesStatus(useOverride=true)&teamId='
        )
        self.NBA_SCOREBOARD_ENDPOINT = (
            "https://data.nba.net/10s/prod/v2/{}/scoreboard.json"
        )
        self.NFL_SCOREBOARD_ENDPOINT = (
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl/"
            "scoreboard?lang=en&region=us&calendartype=blacklist&limit=100"
            "&showAirings=true&dates=2020&seasontype={type}&week={week}"
        )
        self.NFL_AUTH = None
        self.NFL_WEEKS = {
            '2020-09-09': {'week':  1, 'type': 2},
            '2020-09-16': {'week':  2, 'type': 2},
            '2020-09-23': {'week':  3, 'type': 2},
            '2020-09-30': {'week':  4, 'type': 2},
            '2020-10-07': {'week':  5, 'type': 2},
            '2020-10-14': {'week':  6, 'type': 2},
            '2020-10-21': {'week':  7, 'type': 2},
            '2020-10-28': {'week':  8, 'type': 2},
            '2020-11-04': {'week':  9, 'type': 2},
            '2020-11-11': {'week': 10, 'type': 2},
            '2020-11-18': {'week': 11, 'type': 2},
            '2020-11-25': {'week': 12, 'type': 2},
            '2020-12-03': {'week': 13, 'type': 2},
            '2020-12-09': {'week': 14, 'type': 2},
            '2020-12-16': {'week': 15, 'type': 2},
            '2020-12-23': {'week': 16, 'type': 2},
            '2020-12-30': {'week': 17, 'type': 2},
            '2021-01-06': {'week':  1, 'type': 3},
            '2021-01-13': {'week':  2, 'type': 3},
            '2021-01-20': {'week':  3, 'type': 3},
            '2021-01-27': {'week':  4, 'type': 3},
            '2021-02-03': {'week':  5, 'type': 3},
            '2021-02-10': {'week':  6, 'type': 3}
        }

        self.NHL_TEAMS = self._fetch_teams("NHL")
        self.MLB_TEAMS = self._fetch_teams("MLB")
        self.NBA_TEAMS = self._fetch_teams("NBA")

        self.NFL_TEAMS = {
            "ARI": "Arizona Cardinals",
            "ATL": "Atlanta Falcons",
            "BAL": "Baltimore Ravens",
            "BUF": "Buffalo Bills",
            "CAR": "Carolina Panthers",
            "CHI": "Chicago Bears",
            "CIN": "Cincinnati Bengals",
            "CLE": "Cleveland Browns",
            "DAL": "Dallas Cowboys",
            "DEN": "Denver Broncos",
            "DET": "Detroit Lions",
            "GB":  "Green Bay Packers",
            "HOU": "Houston Texans",
            "IND": "Indianapolis Colts",
            "JAX": "Jacksonville Jaguars",
            "KC":  "Kansas City Chiefs",
            "LAC": "Los Angeles Chargers",
            "LAR": "Los Angeles Rams",
            "LV":  "Las Vegas Raiders",
            "MIA": "Miami Dolphins",
            "MIN": "Minnesota Vikings",
            "NE":  "New England Patriots",
            "NO":  "New Orleans Saints",
            "NYG": "New York Giants",
            "NYJ": "New York Jets",
            "PHI": "Philadelphia Eagles",
            "PIT": "Pittsburgh Steelers",
            "SEA": "Seattle Seahawks",
            "SF":  "San Francisco 49ers",
            "TB":  "Tampa Bay Buccaneers",
            "TEN": "Tennessee Titans",
            "WAS": "Washington",
            "WSH": "Washington",
        }

    @staticmethod
    async def fetch_json(url: str):
        async with aiohttp.ClientSession() as cs:
            async with cs.get(url) as r:
                return await r.json()

    @commands.command(name='sports', pass_context=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_all_scores(self, ctx, *, optional_input: str = None):
        """Fetches scores from all available leagues
        (currently NHL, MLB, NBA, and NFL)
        """
        await ctx.invoke(
            self.bot.get_command('nhl'),
            optional_input=optional_input
        )
        await ctx.invoke(
            self.bot.get_command('mlb'),
            optional_input=optional_input
        )
        await ctx.invoke(
            self.bot.get_command('nba'),
            optional_input=optional_input
        )
        await ctx.invoke(
            self.bot.get_command('nfl'),
            optional_input=optional_input
        )

    @commands.command(name='nfl', aliases=['nflscores', 'football'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_nfl_scores(self, ctx, *, optional_input: str = None):
        """Fetches NFL scores from NFL.com"""

        def _next_key(d, key):
            key_iter = iter(d)

            for k in key_iter:
                if k == key:
                    return next(key_iter, "2020-02-10")

            return "2020-02-10"

        now = pendulum.now()
        for week in self.NFL_WEEKS:
            check = pendulum.parse(week, strict=False)
            next_key = _next_key(self.NFL_WEEKS, week)
            print(next_key)
            next_week = pendulum.parse(next_key, strict=False)
            print(check, "\t",
                  now, "\t",
                  next_week, "\t",
                  check < now < next_week)
            if check < now < next_week:
                current_week = self.NFL_WEEKS[week]
                break

        url = self.NFL_SCOREBOARD_ENDPOINT.format(**current_week)
        data = await self.fetch_json(url)

        mobile_output = False
        member = ctx.author
        member_id = str(member.id)
        if member.is_on_mobile():
            mobile_output = True

        user_timezone = self.user_db.get(member_id, {}).get('timezone')
        # LOGGER.debug((user_timezone, self.user_db))

        date = pendulum.now().in_tz(self.default_now_tz).format("YYYY-MM-DD")
        append_team = ""
        team = ""
        timezone = None
        if optional_input:
            args = optional_input.split()
            for idx, arg in enumerate(args):
                if arg == "--tz":
                    # grab the user-defined timezone
                    timezone = args[idx + 1]
                    # see if it's a short-hand timezone first
                    timezone = self.short_tzs.get(timezone.lower()) or timezone
                    # now check if it's valid
                    try:
                        _ = pendulum.timezone(timezone)
                    except Exception:
                        await ctx.send(
                            "Sorry that is an invalid timezone "
                            "(try one from https://nodatime.org/TimeZones)"
                        )
                        return
                if arg.replace("-", "").isdigit():
                    date = arg
                if len(arg.lower()) <= 3:
                    append_team = self.NFL_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if not append_team:
                    for full_name, id_ in self.NFL_TEAMS.items():
                        if arg.lower() in full_name.lower():
                            append_team = id_
                            break
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(
                        user_timezone or
                        self.default_other_tz).format("YYYY-MM-DD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(
                        user_timezone or
                        self.default_other_tz).format("YYYY-MM-DD")

            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(
                    user_timezone or
                    self.default_other_tz).format("YYYY-MM-DD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(
                    user_timezone or
                    self.default_other_tz).format("YYYY-MM-DD")

        LOGGER.debug("NFL API called for: {}".format(url))

        if append_team:
            LOGGER.debug(append_team)

        games = data.get('events', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (NFL)")
            await ctx.send(
                "I couldn't find any NFL games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date)
            )
            return

        sortorder = {"2":  0,
                     "7":  1,
                     "22": 2,
                     "23": 3,
                     "1":  4,
                     "3":  5,
                     "6":  6}
        games.sort(key=lambda x: sortorder.get(x["status"]["type"]["id"], 0))

        games_date = f"Week #{current_week['week']}"
        number_of_games = len(games)

        away = ""
        home = ""
        details = ""
        mobile_output_string = ""
        # series_summary = ""

        for game in games:
            # LOGGER.debug(series_summary)
            game_details = game['competitions'][0]
            odds = game_details.get('odds', {})
            if odds:
                odds = odds[0]
            teams = game_details['competitors']
            away_team = teams[1]['team']['shortDisplayName'] \
                if not mobile_output \
                else teams[1]['team']['abbreviation']
            home_team = teams[0]['team']['shortDisplayName'] \
                if not mobile_output \
                else teams[0]['team']['abbreviation']
            # a_team_emoji = self.bot.get_emoji()
            for tguild in self.bot.guilds:
                if tguild.name == "nfl":
                    guild = tguild
                    break
            a_team_emoji = get(
                guild.emojis,
                name="nfl_"+teams[1]['team']['abbreviation'].lower()) or ""
            h_team_emoji = get(
                guild.emojis,
                name="nfl_"+teams[0]['team']['abbreviation'].lower()) or ""
            if away_team == "Washington":
                away_team = "Football Team"
            if home_team == "Washington":
                home_team = "Football Team"
            combined_names = f"{teams[1]['team']['displayName']} \
                               {teams[0]['team']['displayName']}"

            if game['status']['type']['state'] == 'in':
                score_bug = game['competitions'][0]['competitors']
                situation = game_details.get('situation', {})
                if situation.get('possession'):
                    for team in score_bug:
                        if situation['possession'] == team['id']:
                            if team['homeAway'] == "away":
                                away_team += ":football:"
                            else:
                                home_team += ":football:"
                a_score = int(score_bug[1]['score'])
                h_score = int(score_bug[0]['score'])
                if a_score > h_score:
                    a_score = "**{}**".format(a_score)
                    away_team = "**{}**".format(away_team)
                elif h_score > a_score:
                    h_score = "**{}**".format(h_score)
                    home_team = "**{}**".format(home_team)
                try:
                    ordinal = " " + \
                        game['status']['type']['shortDetail'].split('- ')[1]
                except Exception:
                    ordinal = " _{}_".format(
                        game['status']['type']['shortDetail'])
                if "halftime" in ordinal.lower():
                    ordinal = ""
                if game['status']['type']['shortDetail'] == 'Halftime':
                    time_left = "Halftime"
                else:
                    time_left = game['status']['displayClock']
                time = "__{}__{}".format(
                    time_left,
                    ordinal,
                )
                if not mobile_output:
                    status = "{} - {} [{}]".format(a_score, h_score, time)
                    if append_team:
                        try:
                            if situation.get('downDistanceText'):
                                status += f" - {situation['downDistanceText']}"
                            if situation.get('lastPlay'):
                                status += f"\nPrev. Play: \
                                    {situation['lastPlay']['text']}"
                        except Exception as e:
                            LOGGER.debug(e)
                            pass
                else:
                    status = "[{}]".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)

                # REDZONE
                if situation.get("isRedZone"):
                    status += " 🔴"
            elif game['status']['type']['completed']:
                score_bug = game['competitions'][0]['competitors']
                a_score = int(score_bug[1]['score'])
                h_score = int(score_bug[0]['score'])
                # TODO: redzone
                if a_score > h_score:
                    a_score = "**{}**".format(a_score)
                    away_team = "**{}**".format(away_team)
                elif h_score > a_score:
                    h_score = "**{}**".format(h_score)
                    home_team = "**{}**".format(home_team)
                if game['status']['period'] > 4:
                    filler = '{}'.format(
                        game['status']['period']-4 if
                        game['status']['period'] > 5 else ''
                    )
                    time_left = f"Final/{filler}OT"
                else:
                    time_left = "Final"
                time = "_{}_".format(
                    time_left,
                )
                if not mobile_output:
                    status = "{} - {} {}".format(a_score, h_score, time)
                    # if append_team:
                    #     try:
                    #         status += f" - {situation['downDistanceText']}\n"
                    #         status += f"{situation['lastPlay']['text']}"
                    #     except:
                    #         pass
                else:
                    status = "{}".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)
            elif game['status']['type']['description'] == 'Postponed':
                status = "PPD"
                a_score = ""
                h_score = ""
            else:
                try:
                    game_date = pendulum.parse(game['date']).in_tz(
                        timezone or user_timezone or self.default_tz)
                    today = pendulum.now().in_tz(
                        timezone or user_timezone or self.default_tz)
                    tomorrow = pendulum.tomorrow().in_tz(
                        timezone or user_timezone or self.default_tz)
                    if game_date.is_same_day(today):
                        status = game_date.format(
                            "h:mm A zz"
                        )
                    elif game_date.is_same_day(tomorrow):
                        status = game_date.format(
                            "[Tomorrow], h:mm A zz"
                        )
                    else:
                        status = game_date.format(
                            "dddd, h:mm A zz"
                        )
                    if int(game['status']['period']) > 0:
                        print(today.diff(game_date).in_hours())
                        if today.diff(game_date).in_hours() <= 1:
                            # Pre-game
                            status += " [Warmup]"
                            # if not append_team:
                            #     away_team += "\n"
                            #     home_team += "\n"
                except Exception:
                    status = ""
                if append_team and odds:
                    LOGGER.debug(odds)
                    status += f"\n(Odds: {odds.get('details', '')}, \
                                       ⇕ {odds.get('overUnder', '')})"
                a_score = ""
                h_score = ""

            away_team = "{}{}".format(a_team_emoji, away_team)
            home_team = "{}{}".format(h_team_emoji, home_team)
            blank = get(ctx.guild.emojis, name="blank") or ""
            if append_team:
                if append_team in combined_names:
                    number_of_games = 1
                    if mobile_output:
                        mobile_output_string += "{}{} @ {}{}  |  {}\n".format(
                            away_team, a_score,
                            home_team, h_score,
                            status
                        )
                    else:
                        away_team += "\n"
                        home_team += "\n"
                        away += away_team
                        home += home_team
                        # if series_summary:
                        #     status += f" - {series_summary}"
                        status = f"{status}{blank}\n"
                        details += status
            else:
                if mobile_output:
                    mobile_output_string += "‣ {}{} @ {}{}  |  {}\n".format(
                        away_team, a_score,
                        home_team, h_score,
                        status
                    )
                else:
                    away_team += "\n"
                    home_team += "\n"
                    away += away_team
                    home += home_team
                    # if series_summary:
                    #     status += f" - {series_summary}"
                    status = f"{status}{blank}\n"
                    details += status

        # print(away, home, mobile_output_string)
        if mobile_output:
            if not mobile_output_string:
                await ctx.send(
                    "I couldn't find any NFL games for {team}{date}.".format(
                        team="{} during Week #".format(team) if team else "",
                        date=current_week)
                )
                return
        else:
            if not away and not home:
                await ctx.send(
                    "I couldn't find any NFL games for {team}{date}.".format(
                        team="{} during Week #".format(team) if team else "",
                        date=current_week)
                )
                return

        embed_data = {
            "league":          "NFL",
            "games_date":      games_date,
            "number_of_games": number_of_games,
            "mobile":          mobile_output_string,
            "away":            away,
            "home":            home,
            "status":          details,
            "copyright":       "",
            "icon":            ("https://static.www.nfl.com/image/upload/"
                                "v1554321393/league/nvfr7ogywskqrfaiu38m.png"),
            "thumbnail":       ("https://static.www.nfl.com/image/upload/"
                                "v1554321393/league/nvfr7ogywskqrfaiu38m.png"),
        }

        # embed = self._build_embed(embed_data, mobile_output, 0x003069)

        if timezone:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['timezone'] = timezone
            self._save()

        # this is really dumb and brute force way to split the games up over
        # multiple embeds because discord doesn't like fields that are greater
        # than 1024 characters in length.
        # TODO: clean this shit up
        # TODO: refactor _build_embed to be smarter
        LOGGER.warn(len(embed_data['mobile']))
        multi = False  # flag for later on, output multiple embeds
        if mobile_output:
            # this is the real snag, since i only use one field for mobile
            # output, it gets large when many games are scheduled
            max_length = 1024
            if len(embed_data['mobile']) > 1024:
                # we only need to do this if we're over the limit
                cur_length = 0
                lines = embed_data['mobile'].split("\n")
                tmp = ""
                for idx, line in enumerate(lines):
                    # go over the list and only add back each line until we're
                    # at or close to the limit
                    cur_length += len(line)
                    if cur_length <= max_length:
                        # add the line since we're still under 1024
                        tmp += line + "\n"
                    else:
                        # we're over, break the loop to perserve idx
                        break
                # idx allows us to add the rest of the games where we left off
                # for the 2nd embed
                rest = "\n".join(lines[idx:])
                # LOGGER.warn(rest)
                multi = True  # set our multiple embed flag to true
                embed_data = {
                    "league":          "NFL",
                    "games_date":      games_date,
                    "number_of_games": number_of_games,
                    "mobile":          tmp,
                    "away":            away,
                    "home":            home,
                    "status":          details,
                    "copyright":       "",
                    "icon":            ("https://static.www.nfl.com/image/"
                                        "upload/v1554321393/league/"
                                        "nvfr7ogywskqrfaiu38m.png"),
                    "thumbnail":       ("https://static.www.nfl.com/image/"
                                        "upload/v1554321393/league/"
                                        "nvfr7ogywskqrfaiu38m.png"),
                }
                # create the first embed, this is where refactoring the build
                # embed code would come in handy
                embed1 = self._build_embed(embed_data, mobile_output, 0x003069)
                embed_data = {
                    "league":          "NFL",
                    "title":           "",
                    "description":     "",
                    "multi":           True,
                    "games_date":      games_date,
                    "number_of_games": number_of_games,
                    "mobile":          rest,
                    "away":            away,
                    "home":            home,
                    "status":          details,
                    "copyright":       "",
                    "icon":            ("https://img.cottongin.xyz/"
                                        "i/4tk9zpfl.png"),
                    "thumbnail":       ("https://img.cottongin.xyz/"
                                        "i/4tk9zpfl.png"),
                }
                # create number two
                embed2 = self._build_embed(embed_data, mobile_output, 0x003069)
            else:
                embed = self._build_embed(embed_data, mobile_output, 0x003069)
        else:
            embed = self._build_embed(embed_data, mobile_output, 0x003069)

        if multi:
            await ctx.send(embed=embed1)
            await ctx.send(embed=embed2)
        else:
            await ctx.send(embed=embed)

        # await ctx.send(embed=embed)

    @commands.command(name='nhl', aliases=['nhlscores', 'hockey'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_nhl_scores(self, ctx, *, optional_input: str = None):
        """Fetches NHL scores from NHL.com

        • [optional_input] can be in the form of a specific team's tricode
            or a date, or both
        • You can add "--tz custom timezone" to return results in your timezone
            I will remember the last custom timezone you asked for, so there
            is no need to add it every time.

        e.g. nhl bos 2020-08-03
             nhl bos yesterday
             nhl tomorrow
             nhl --tz US/Pacific
             nhl --tz pdt bos
        """

        mobile_output = False
        member = ctx.author
        member_id = str(member.id)
        if member.is_on_mobile():
            mobile_output = True

        user_timezone = self.user_db.get(member_id, {}).get('timezone')
        # LOGGER.debug((user_timezone, self.user_db))

        date = pendulum.now().in_tz(self.default_now_tz).format("YYYY-MM-DD")
        append_team = ""
        team = ""
        timezone = None
        if optional_input:
            args = optional_input.split()
            for idx, arg in enumerate(args):
                if arg == "--tz":
                    # grab the user-defined timezone
                    timezone = args[idx + 1]
                    # see if it's a short-hand timezone first
                    timezone = self.short_tzs.get(timezone.lower()) or timezone
                    # now check if it's valid
                    try:
                        _ = pendulum.timezone(timezone)
                    except Exception:
                        await ctx.send(
                            "Sorry that is an invalid timezone "
                            "(try one from https://nodatime.org/TimeZones)")
                        return
                if arg.replace("-", "").isdigit():
                    date = arg
                if len(arg.lower()) <= 3:
                    append_team = self.NHL_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if not append_team:
                    for full_name, id_ in self.NHL_TEAMS.items():
                        if arg.lower() in full_name.lower():
                            append_team = id_
                            break
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(
                        user_timezone or
                        self.default_other_tz).format("YYYY-MM-DD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(
                        user_timezone or
                        self.default_other_tz).format("YYYY-MM-DD")

            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(
                    user_timezone or
                    self.default_other_tz).format("YYYY-MM-DD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(
                    user_timezone or
                    self.default_other_tz).format("YYYY-MM-DD")

        url = "{}{}".format(
            self.NHL_SCOREBOARD_ENDPOINT.format(date, date),
            append_team)
        LOGGER.debug("NHL API called for: {}".format(url))

        # data = requests.get(url).json()
        data = await self.fetch_json(url)
        games = data.get('dates', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (NHL)")
            await ctx.send(
                "I couldn't find any NHL games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date)
            )
            return
        else:
            games = games[0].get('games', {})
            if not games:
                LOGGER.warn("Something went wrong possibly. (NHL)")
                await ctx.send(
                    "I couldn't find any NHL games for {team}{date}.".format(
                        team="{} on ".format(team) if team else "",
                        date=date)
                )
                return

        games_date = pendulum.parse(games[0]['gameDate']).in_tz(
            self.default_other_tz).format("MMM Do")
        number_of_games = len(games)
        # types_of_games = {
        #     'P': ' **PLAYOFF** ',
        #     'R': ' Regular season ',
        #     'Pre': ' Pre-season ',
        # }
        # type_ = types_of_games.get(games[0]['gameType'], ' ')

        away = ""
        home = ""
        details = ""
        mobile_output_string = ""
        series_summary = ""

        for game in games:
            if game.get("gameType", "") == "P":
                # if we're a playoff game?
                if game.get("seriesSummary"):
                    series_summary = game["seriesSummary"]["seriesStatusShort"]
            LOGGER.debug(series_summary)
            away_team = game['teams']['away']['team']['teamName'] \
                if not mobile_output \
                else game['teams']['away']['team']['abbreviation']
            home_team = game['teams']['home']['team']['teamName'] \
                if not mobile_output \
                else game['teams']['home']['team']['abbreviation']
            for tguild in self.bot.guilds:
                if tguild.name == "nhl":
                    guild = tguild
                    break
            a = "nhl_" + game['teams']['away']['team']['abbreviation'].lower()
            a_team_emoji = get(guild.emojis, name=a)
            h = "nhl_"+game['teams']['home']['team']['abbreviation'].lower()
            h_team_emoji = get(guild.emojis, name=h)
            if a_team_emoji:
                if "mtl" in a:
                    a_team_emoji = "💩 "
                a_team_emoji = "{} ".format(a_team_emoji)
            else:
                a_team_emoji = ""
            if h_team_emoji:
                if "mtl" in h:
                    h_team_emoji = "💩 "
                h_team_emoji = "{} ".format(h_team_emoji)
            else:
                h_team_emoji = ""
            if game['status']['abstractGameState'] == 'Live':
                score_bug = game['linescore']
                a_score = score_bug['teams']['away']['goals']
                h_score = score_bug['teams']['home']['goals']
                if score_bug['teams']['away'].get('powerPlay'):
                    away_team += " (**PP {}**)".format(
                        self._convert_seconds(
                          score_bug['powerPlayInfo']['situationTimeRemaining'])
                    )
                if score_bug['teams']['home'].get('powerPlay'):
                    home_team += " (**PP {}**)".format(
                        self._convert_seconds(
                          score_bug['powerPlayInfo']['situationTimeRemaining'])
                    )
                if a_score > h_score:
                    a_score = "**{}**".format(a_score)
                    away_team = "**{}**".format(away_team)
                elif h_score > a_score:
                    h_score = "**{}**".format(h_score)
                    home_team = "**{}**".format(home_team)
                time = "__{}__ {}".format(
                    score_bug['currentPeriodTimeRemaining'],
                    score_bug['currentPeriodOrdinal']
                )
                if score_bug['intermissionInfo'].get('inIntermission'):
                    int_remains = score_bug['intermissionInfo'].get(
                        'intermissionTimeRemaining'
                    )
                    if int_remains > 0:
                        time += " **INT {}**".format(
                            self._convert_seconds(int_remains)
                        )
                if not mobile_output:
                    status = "{} - {} [{}]".format(a_score, h_score, time)
                else:
                    status = "[{}]".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)
            elif game['status']['abstractGameState'] == 'Final':
                score_bug = game['linescore']
                a_score = score_bug['teams']['away']['goals']
                h_score = score_bug['teams']['home']['goals']
                if a_score > h_score:
                    a_score = "**{}**".format(a_score)
                    away_team = "**{}**".format(away_team)
                elif h_score > a_score:
                    h_score = "**{}**".format(h_score)
                    home_team = "**{}**".format(home_team)
                time = "_Final_"  # if not mobile_output else "_F_"
                if game['linescore']['currentPeriod'] >= 4:
                    time = "_Final/OT_"  # if not mobile_output else "_F/OT_"
                if not mobile_output:
                    status = "{} - {} {}".format(a_score, h_score, time)
                else:
                    status = "{}".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)
            elif game['status']['detailedState'] == 'Postponed':
                status = "PPD"
                a_score = ""
                h_score = ""
            else:
                try:
                    status = pendulum.parse(game['gameDate']).in_tz(
                        timezone or user_timezone or self.default_tz).format(
                        "h:mm A zz"
                    )
                    if int(game['status']['codedGameState']) == 2:
                        # Pre-game
                        status += " [Warmup]"
                    if "AM" == pendulum.parse(game['gameDate']).in_tz(
                        self.default_tz).format("A") and \
                       int(status.split(":")[0]) < 10:
                        status = "Time TBD"
                except Exception:
                    status = ""
                a_score = ""
                h_score = ""

            away_team = "{}{}".format(a_team_emoji, away_team)
            home_team = "{}{}".format(h_team_emoji, home_team)
            blank = get(ctx.guild.emojis, name="blank")
            if mobile_output:
                mobile_output_string += "{}{} @ {}{}  |  {}\n".format(
                    away_team, a_score,
                    home_team, h_score,
                    status
                )
            else:
                away_team += "\n"
                home_team += "\n"
                away += away_team
                home += home_team
                if series_summary:
                    status += f" - {series_summary}"
                status = f"{status}{blank}\n"
                details += status

        embed_data = {
            "league":          "NHL",
            "games_date":      games_date,
            "number_of_games": number_of_games,
            "mobile":          mobile_output_string,
            "away":            away,
            "home":            home,
            "status":          details,
            "copyright":       data['copyright'],
            "icon":            ("http://assets.stickpng.com/thumbs/"
                                "5a4fbb7bda2b4f099b95da15.png"),
            "thumbnail":       ("http://assets.stickpng.com/thumbs/"
                                "5a4fbb7bda2b4f099b95da15.png"),
        }

        embed = self._build_embed(embed_data, mobile_output, 0x95A3AE)

        if timezone:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['timezone'] = timezone
            self._save()

        await ctx.send(embed=embed)

    @commands.command(name='mlb', aliases=['mlbscores', 'baseball'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_mlb_scores(self, ctx, *, optional_input: str = None):
        """Fetches MLB scores from MLB.com

        • [optional_input] can be in the form of a specific team's tricode or a
            date, or both
        • You can add "--tz custom timezone" to return results in your
            timezone. I will remember the last custom timezone you asked for,
            so there is no need to add it every time.

        e.g. mlb bos 2020-08-03
             mlb bos yesterday
             mlb tomorrow
             mlb --tz US/Central
             mlb --tz cst bos
        """

        mobile_output = False
        member = ctx.author
        member_id = str(member.id)
        if member.is_on_mobile():
            mobile_output = True

        user_timezone = self.user_db.get(member_id, {}).get('timezone')
        LOGGER.debug((user_timezone))

        date = pendulum.now().in_tz(self.default_now_tz).format("YYYY-MM-DD")
        append_team = ""
        team = ""
        timezone = None
        if optional_input:
            args = optional_input.split()
            for idx, arg in enumerate(args):
                if arg == "--tz":
                    # grab the user-defined timezone
                    timezone = args[idx + 1]
                    # see if it's a short-hand timezone first
                    timezone = self.short_tzs.get(timezone.lower()) or timezone
                    # now check if it's valid
                    try:
                        _ = pendulum.timezone(timezone)
                    except Exception:
                        await ctx.send(
                            "Sorry that is an invalid timezone "
                            "(try one from https://nodatime.org/TimeZones)")
                        return
                if arg.replace("-", "").isdigit():
                    date = arg
                if len(arg.lower()) <= 3:
                    append_team = self.MLB_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if not append_team:
                    for full_name, id_ in self.MLB_TEAMS.items():
                        if arg.lower() in full_name.lower():
                            append_team = id_
                            break
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(
                        user_timezone or self.default_other_tz).format(
                            "YYYY-MM-DD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(
                        user_timezone or self.default_other_tz).format(
                            "YYYY-MM-DD")

            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(
                    user_timezone or self.default_other_tz).format(
                        "YYYY-MM-DD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(
                    user_timezone or self.default_other_tz).format(
                        "YYYY-MM-DD")

        url = self.MLB_SCOREBOARD_ENDPOINT.format(date) + str(append_team)
        LOGGER.debug("MLB API called for: {}".format(url))

        # data = requests.get(url).json()
        data = await self.fetch_json(url)
        games = data.get('dates', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (MLB: fetching games)")
            await ctx.send(
                "I couldn't find any MLB games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date)
            )
            return
        else:
            games = games[0].get('games', {})
            if not games:
                LOGGER.warn("Something went wrong. (MLB: fetching games)")
                await ctx.send(
                    "I couldn't find any MLB games for {team}{date}.".format(
                        team="{} on ".format(team) if team else "",
                        date=date)
                )
                return

        # MLB.com API datetime population for doubleheaders is a JOKE.
        # This hack just matches up games and manually sets the time to +5 mins
        # for easier sorting.
        for game in games:
            if game['doubleHeader'] and game['gameNumber'] == 2:
                # this game is often populated with bogus start time data,
                # e.g. "11:33pm"
                for _ in games:
                    # now iterate over the entire list again and find the
                    # matching game with the right teams but also game 1 of
                    # the doubleheader
                    check_id = game['teams']['away']['team']['id']
                    _away_id = _['teams']['away']['team']['id']
                    _home_id = _['teams']['home']['team']['id']
                    if check_id == _away_id or check_id == _home_id:
                        if _['doubleHeader'] and _['gameNumber'] == 1:
                            # finally, hack the start time and move on
                            game['gameDate'] = pendulum.parse(
                                _['gameDate']).to_iso8601_string()
                            break

        # now sort everything by start time first, then put the finished games
        # at the end (or postponed ones), and the ones in progress up top.
        status_sortorder = {
            "Live":    0,
            "Preview": 1,
            "Final":   2
        }
        games.sort(key=lambda x: (x['gameDate']))
        games.sort(
            key=lambda x: status_sortorder[x["status"]["abstractGameState"]])

        games_date = pendulum.parse(games[0]['gameDate']).in_tz(
            self.default_other_tz).format('MMM Do \'YY')
        number_of_games = len(games)
        # types_of_games = {
        #     'P': ' **PLAYOFF** ',
        #     'R': ' Regular season ',
        #     'Pre': ' Pre-season ',
        # }
        # type_ = types_of_games.get(games[0]['gameType'], ' ')

        away = ""
        home = ""
        details = ""
        mobile_output_string = ""

        statuses = {
            "Postponed": "PPD",
            "COVID-19": "COVID",
            "UNK": "",
            "DO": ""
        }
        ppd_away = ""
        ppd_home = ""
        ppd_details = ""
        ppd_games_mobile = ""
        content = ""

        for game in games:
            if not content:
                content = "\n{}".format(
                    game.get('seriesStatus', {}).get('result')
                )
            else:
                content += " | {}".format(
                    game.get('seriesStatus', {}).get('result')
                )
            postponed = False
            if mobile_output:
                away_team = game['teams']['away']['team']['abbreviation']
                home_team = game['teams']['home']['team']['abbreviation']
            else:
                away_team = game['teams']['away']['team']['teamName']
                home_team = game['teams']['home']['team']['teamName']
            a = "mlb_"+game['teams']['away']['team']['abbreviation'].lower()
            h = "mlb_"+game['teams']['home']['team']['abbreviation'].lower()
            for tguild in self.bot.guilds:
                if tguild.name == "mlb":
                    guild = tguild
                    break
            a_team_emoji = get(guild.emojis, name=a)
            h_team_emoji = get(guild.emojis, name=h)
            if a_team_emoji:
                if "nyy" in a:
                    a_team_emoji = "💩 "
                a_team_emoji = "{} ".format(a_team_emoji)
            else:
                a_team_emoji = ""
            if h_team_emoji:
                if "nyy" in h:
                    h_team_emoji = "💩 "
                h_team_emoji = "{} ".format(h_team_emoji)
            else:
                h_team_emoji = ""
            if game['status']['abstractGameState'] == 'Live':
                if game['status']['detailedState'] == 'Warmup':
                    try:
                        checktz = timezone or user_timezone or self.default_tz
                        status = pendulum.parse(
                            game['gameDate']).in_tz(checktz).format(
                            "h:mm A zz"
                        )
                        tbd_check = pendulum.parse(
                            game['gameDate']).in_tz("US/Eastern").format(
                            "h:mm A zz"
                        )
                        if "AM" in tbd_check:
                            status = "Time TBD"
                    except Exception:
                        status = ""
                    a_score = ""
                    h_score = ""
                    status += " [Warmup]"
                else:
                    score_bug = game['linescore']
                    a_score = score_bug['teams']['away']['runs']
                    h_score = score_bug['teams']['home']['runs']
                    if a_score > h_score:
                        a_score = "**{}**".format(a_score)
                        away_team = "**{}**".format(away_team)
                    elif h_score > a_score:
                        h_score = "**{}**".format(h_score)
                        home_team = "**{}**".format(home_team)
                    if score_bug['inningHalf'].lower() == "top":
                        inning = ":arrow_up:"
                    elif score_bug['inningHalf'].lower() == "bottom":
                        inning = ":arrow_down:"
                    else:
                        inning = score_bug['inningHalf']
                    time = "{} {}".format(
                        inning,
                        score_bug['currentInningOrdinal']
                    )
                    if not mobile_output:
                        status = "{} - {} [{}]".format(a_score, h_score, time)
                    else:
                        status = "[{}]".format(time)
                        a_score = " {}".format(a_score)
                        h_score = " {}".format(h_score)
                    if game.get("resumedFrom"):
                        if not mobile_output:
                            status += " (Resumed from {})".format(
                                pendulum.parse(game['resumedFrom']).format(
                                    "MMM Do")
                            )
                        else:
                            status += " (orig: {})".format(
                                pendulum.parse(game['resumedFrom']).format(
                                    "M/D")
                            )
            elif game['status']['abstractGameState'] == 'Final':
                score_bug = game.get('linescore', {})
                if not score_bug:
                    status = "{}{}".format(
                        statuses.get(
                            game['status']['detailedState'], "UNK"),
                        "/"+game['status'].get('reason')
                        if game['status'].get('reason') else "")
                    away_team = self._strikethrough(away_team)
                    home_team = self._strikethrough(home_team)
                    a_score = ""
                    h_score = ""
                    if "PPD" in status:
                        postponed = True
                else:
                    a_score = score_bug['teams']['away'].get('runs', "")
                    h_score = score_bug['teams']['home'].get('runs', "")
                    if a_score > h_score:
                        a_score = "**{}**".format(a_score)
                        away_team = "**{}**".format(away_team)
                    elif h_score > a_score:
                        h_score = "**{}**".format(h_score)
                        home_team = "**{}**".format(home_team)
                    time = "_Final_"
                    if game['linescore']['currentInning'] != 9:
                        time = "_Final/{}_".format(
                            game['linescore']['currentInning'])
                    if not mobile_output:
                        status = "{} - {} {}".format(a_score, h_score, time)
                    else:
                        status = "{}".format(time)
                        a_score = " {}".format(a_score)
                        h_score = " {}".format(h_score)
            else:
                try:
                    checktz = timezone or user_timezone or self.default_tz
                    status = pendulum.parse(
                        game['gameDate']).in_tz(checktz).format(
                        "h:mm A zz"
                    )
                    if "AM" in status:
                        status = "Time TBD"
                    if game['doubleHeader'] and game['gameNumber'] == 2:
                        # whether it's from the start time hack above, or
                        # direct from MLB.com API, this data is usually bogus
                        # so let's just set it to something more relevant
                        status = "Game 2"
                except Exception:
                    status = ""
                a_score = ""
                h_score = ""

            away_team = "{}{}".format(a_team_emoji, away_team)
            home_team = "{}{}".format(h_team_emoji, home_team)
            blank = get(ctx.guild.emojis, name="blank")
            if mobile_output:
                if not postponed:
                    mobile_output_string += "{}{} @ {}{}  |  {}\n".format(
                        away_team, a_score,
                        home_team, h_score,
                        status
                    )
                else:
                    ppd_games_mobile += "{}{} @ {}{}  |  {}\n".format(
                        away_team, a_score,
                        home_team, h_score,
                        status
                    )
            else:
                if not postponed:
                    away_team += "\n"
                    home_team += "\n"
                    away += away_team
                    home += home_team
                    status = f"{status}{blank}\n"
                    details += status
                else:
                    away_team += "\n"
                    home_team += "\n"
                    ppd_away += away_team
                    ppd_home += home_team
                    status = f"{status}{blank}\n"
                    ppd_details += status

        embed_data = {
            "league":          "MLB",
            "games_date":      games_date,
            "number_of_games": number_of_games,
            "mobile":          mobile_output_string,
            "away":            away,
            "home":            home,
            "status":          details,
            "content":         content,
            "copyright":       data['copyright'],
            "icon":            "https://img.cottongin.xyz/i/4tk9zpfl.png",
            "thumbnail":       "https://img.cottongin.xyz/i/4tk9zpfl.png",
        }

        # this is really dumb and brute force way to split the games up over
        # multiple embeds because discord doesn't like fields that are greater
        # than 1024 characters in length.
        # TODO: clean this shit up
        # TODO: refactor _build_embed to be smarter
        LOGGER.warn(len(embed_data['mobile']))
        multi = False  # flag for later on, output multiple embeds
        if mobile_output:
            # this is the real snag, since i only use one field for mobile
            # output, it gets large when many games are scheduled
            max_length = 1024
            if len(embed_data['mobile']) > 1024:
                # we only need to do this if we're over the limit
                cur_length = 0
                lines = embed_data['mobile'].split("\n")
                tmp = ""
                for idx, line in enumerate(lines):
                    # go over the list and only add back each line until we're
                    # at or close to the limit
                    cur_length += len(line)
                    if cur_length <= max_length:
                        # add the line since we're still under 1024
                        tmp += line + "\n"
                    else:
                        # we're over, break the loop to perserve idx
                        break
                # idx allows us to add the rest of the games where we left off
                # for the 2nd embed
                rest = "\n".join(lines[idx:])
                # LOGGER.warn(rest)
                multi = True  # set our multiple embed flag to true
                embed_data = {
                    "league":          "MLB",
                    "games_date":      games_date,
                    "number_of_games": number_of_games,
                    "mobile":          tmp,
                    "away":            away,
                    "home":            home,
                    "status":          details,
                    "copyright":       data['copyright'],
                    "icon":         "https://img.cottongin.xyz/i/4tk9zpfl.png",
                    "thumbnail":    "https://img.cottongin.xyz/i/4tk9zpfl.png",
                }
                # create the first embed, this is where refactoring the build
                # embed code would come in handy
                embed1 = self._build_embed(embed_data, mobile_output, 0xCD0001)
                embed_data = {
                    "league":          "MLB",
                    "title":           "",
                    "description":     "",
                    "multi":           True,
                    "games_date":      games_date,
                    "number_of_games": number_of_games,
                    "mobile":          rest,
                    "away":            away,
                    "home":            home,
                    "status":          details,
                    "copyright":       data['copyright'],
                    "icon":         "https://img.cottongin.xyz/i/4tk9zpfl.png",
                    "thumbnail":    "https://img.cottongin.xyz/i/4tk9zpfl.png",
                }
                # create number two
                embed2 = self._build_embed(embed_data, mobile_output, 0xCD0001)
            else:
                embed = self._build_embed(embed_data, mobile_output, 0xCD0001)
        else:
            embed = self._build_embed(embed_data, mobile_output, 0xCD0001)

        if ppd_details or ppd_games_mobile:
            ppd_embed_data = {
                "postponed":       True,
                "ppd":             [ppd_away, ppd_home, ppd_details],
                "ppd_mobile":      ppd_games_mobile,
                "title":           "Postponed Games",
            }
            ppd_embed = self._build_embed(
                ppd_embed_data, mobile_output, 0xCD0001)

        if timezone:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['timezone'] = timezone
            self._save()

        memes = [
            "COVID19 gonna cancel this shit",
            "Rob Manfred is a joke",
            "imagine trading Mookie Betts",
            "The Astros are a bunch of cheaters",
            "FUCK THE YANKEES",
            "imagine 60 games counting as a 'full season'",
        ]

        if multi:
            await ctx.send(
                content='**{}**'.format(random.choice(memes)), embed=embed1)
            await ctx.send(embed=embed2)
        else:
            await ctx.send(
                content='**{}**'.format(random.choice(memes)), embed=embed)
        if ppd_details:
            await ctx.send(embed=ppd_embed)

    @commands.command(name='nba', aliases=['nbascores', 'basketball'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_nba_scores(self, ctx, *, optional_input: str = None):
        """Fetches NBA scores from NBA.com

        • [optional_input] can be in the form of a specific team's tricode or a
            date, or both
        • You can add "--tz custom timezone" to return results in your
            timezone. I will remember the last custom timezone you asked for,
            so there is no need to add it every time.

        e.g. nba bos 2020-08-03
             nba bos yesterday
             nba tomorrow
             nba --tz US/Mountain
             nba --tz mst bos
        """

        mobile_output = False
        member = ctx.author
        member_id = str(member.id)
        if member.is_on_mobile():
            mobile_output = True

        user_timezone = self.user_db.get(member_id, {}).get('timezone')
        # LOGGER.debug((user_timezone, self.user_db))

        date = pendulum.now().in_tz(self.default_now_tz).format("YYYYMMDD")
        append_team = ""
        team = ""
        timezone = None
        if optional_input:
            args = optional_input.split()
            for idx, arg in enumerate(args):
                if arg == "--tz":
                    # grab the user-defined timezone
                    timezone = args[idx + 1]
                    # see if it's a short-hand timezone first
                    timezone = self.short_tzs.get(timezone.lower()) or timezone
                    # now check if it's valid
                    try:
                        _ = pendulum.timezone(timezone)
                    except Exception:
                        await ctx.send(
                            "Sorry that is an invalid timezone "
                            "(try one from https://nodatime.org/TimeZones)")
                        return
                if arg.replace("-", "").isdigit():
                    date = arg.replace("-", "")
                if len(arg.lower()) <= 3:
                    append_team = self.NBA_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if not append_team:
                    for full_name, id_ in self.NBA_TEAMS.items():
                        if arg.lower() in full_name.lower():
                            append_team = id_
                            team = id_.upper()
                            break
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(
                        user_timezone or self.default_other_tz).format(
                            "YYYYMMDD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(
                        user_timezone or self.default_other_tz).format(
                            "YYYYMMDD")

            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(
                    user_timezone or self.default_other_tz).format("YYYYMMDD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(
                    user_timezone or self.default_other_tz).format("YYYYMMDD")

        url = self.NBA_SCOREBOARD_ENDPOINT.format(date)
        LOGGER.debug("NBA API called for: {}".format(url))

        # data = requests.get(url).json()
        data = await self.fetch_json(url)
        games = data.get('games', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (NBA: fetching games)")
            await ctx.send(
                "I couldn't find any NBA games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date)
            )
            return

        sortorder = {2: 0, 1: 1, 3: 2}
        games.sort(key=lambda x: sortorder[x["statusNum"]])

        games_date = pendulum.parse(games[0]['startTimeUTC']).in_tz(
            self.default_other_tz).format('MMM Do \'YY')
        # number_of_games = len(games)

        away = ""
        home = ""
        details = ""
        mobile_output_string = ""

        games_found = 0
        for game in games:
            if mobile_output:
                away_team = game['vTeam']['triCode']
                home_team = game['hTeam']['triCode']
            else:
                away_team = self.NBA_TEAMS[game['vTeam']['triCode']]
                home_team = self.NBA_TEAMS[game['hTeam']['triCode']]
            a = "nba_"+game['vTeam']['triCode'].lower()
            h = "nba_"+game['hTeam']['triCode'].lower()
            for tguild in self.bot.guilds:
                if tguild.name == "nba":
                    guild = tguild
                    break
            a_team_emoji = get(guild.emojis, name=a)
            h_team_emoji = get(guild.emojis, name=h)
            blank = get(ctx.guild.emojis, name="blank")
            if a_team_emoji:
                if "lal" in a:
                    a_team_emoji = "💩 "
                a_team_emoji = "{} ".format(a_team_emoji)
            else:
                a_team_emoji = ""
            if h_team_emoji:
                if "lal" in h:
                    h_team_emoji = "💩 "
                h_team_emoji = "{} ".format(h_team_emoji)
            else:
                h_team_emoji = ""
            if game['statusNum'] == 2:
                a_score = int(game['vTeam']['score'])
                h_score = int(game['hTeam']['score'])
                if a_score > h_score:
                    a_score = "**{}**".format(a_score)
                    away_team = "**{}**".format(away_team)
                elif h_score > a_score:
                    h_score = "**{}**".format(h_score)
                    home_team = "**{}**".format(home_team)
                time = "__{}__ Q{}".format(
                    game['clock'] if game['clock'] else "END",
                    game['period']['current']
                )
                if game['period']['isHalftime']:
                    time = "__Halftime__"
                if game['isBuzzerBeater']:
                    time += " :rotating_light:"
                if not mobile_output:
                    status = "{} - {} [{}]".format(a_score, h_score, time)
                else:
                    status = "[{}]".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)
            elif game['statusNum'] == 3:
                a_score = int(game['vTeam']['score'])
                h_score = int(game['hTeam']['score'])
                if a_score > h_score:
                    a_score = "**{}**".format(a_score)
                    away_team = "**{}**".format(away_team)
                elif h_score > a_score:
                    h_score = "**{}**".format(h_score)
                    home_team = "**{}**".format(home_team)
                time = "_Final_"
                if game['period']['current'] > 4:
                    time = "_Final/{}OT_".format(
                        "" if game['period']['current'] == 5 else
                        game['period']['current'] - 4)
                if not mobile_output:
                    status = "{} - {} {}".format(a_score, h_score, time)
                else:
                    status = "{}".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)
            elif game.get('extendedStatusNum', 0) == 2:
                status = "PPD"
                a_score = ""
                h_score = ""
            else:
                try:
                    status = pendulum.parse(game['startTimeUTC']).in_tz(
                        timezone or user_timezone or self.default_tz).format(
                        "h:mm A zz"
                    )
                    if game['isGameActivated']:
                        status += " [Warmup]"
                except Exception:
                    status = ""
                a_score = ""
                h_score = ""

            if game.get('nugget', {}).get('text', {}):
                nugget = game['nugget']['text']
                if team:
                    status += f" - {nugget}"

            away_team = "{}{}".format(a_team_emoji, away_team)
            home_team = "{}{}".format(h_team_emoji, home_team)
            if team:
                if team == game['vTeam']['triCode'] or \
                   team == game['hTeam']['triCode']:
                    if mobile_output:
                        mobile_output_string += "{}{} @ {}{}  |  {}\n".format(
                            away_team, a_score,
                            home_team, h_score,
                            status
                        )
                    else:
                        away_team += "\n"
                        home_team += "\n"
                        away += away_team
                        home += home_team
                        status = f"{status}{blank}\n"
                        details += status
                    games_found += 1
            else:
                if mobile_output:
                    mobile_output_string += "{}{} @ {}{}  |  {}\n".format(
                        away_team, a_score,
                        home_team, h_score,
                        status
                    )
                else:
                    away_team += "\n"
                    home_team += "\n"
                    away += away_team
                    home += home_team
                    status = f"{status}{blank}\n"
                    details += status
                games_found += 1

        if games_found == 0:
            await ctx.send(
                "I couldn't find any NBA games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date)
            )
            return

        content = ""
        if games[0].get("playoffs"):
            content = "\n{}".format(games[0]["playoffs"]["seriesSummaryText"])

        embed_data = {
            "league":          "NBA",
            "games_date":      games_date,
            "number_of_games": games_found,
            "mobile":          mobile_output_string,
            "away":            away,
            "home":            home,
            "status":          details,
            "content":         content,
            "copyright":       "",
            "icon":            ("https://cdn.freebiesupply.com/images/large/"
                                "2x/nba-logo-transparent.png"),
            "thumbnail":       ("https://cdn.freebiesupply.com/images/large/"
                                "2x/nba-logo-transparent.png"),
        }

        embed = self._build_embed(embed_data, mobile_output, 0x17408B)

        if timezone:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['timezone'] = timezone
            self._save()

        await ctx.send(embed=embed)

###
# Helpers
###

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

    def _convert_seconds(self, secs):
        time_left = time.strftime("%M:%S", time.gmtime(secs))
        if time_left[0] == "0":
            return time_left[1:]
        else:
            return time_left

    def _build_embed(self, data, mobile=False, color=0x98FB98):
        if data.get("postponed"):
            embed = discord.Embed(
                title=data['title'],
                colour=color
            )
            if mobile:
                embed.add_field(
                    name='Games',
                    value=data['ppd_mobile'],
                    inline=True)
            else:
                embed.add_field(
                    name='Away',
                    value=data['ppd'][0],
                    inline=True)
                embed.add_field(
                    name='Home',
                    value=data['ppd'][1],
                    inline=True)
                embed.add_field(
                    name='Status',
                    value=data['ppd'][2],
                    inline=True)
        elif data.get("multi"):
            embed = discord.Embed(
                # title=data['title'],
                colour=color
            )
            if mobile:
                embed.add_field(
                    name='Games (continued)',
                    value=data['mobile'],
                    inline=True)
            else:
                embed.add_field(name='Away', value=data['away'], inline=True)
                embed.add_field(name='Home', value=data['home'], inline=True)
                embed.add_field(
                    name='Status',
                    value=data['status'],
                    inline=True)
        else:
            desc = '{num}{type}game{s} {are_or_is} scheduled{content}'
            embed = discord.Embed(
                title='{league} Scores for {date}'.format(
                    league=data['league'], date=data['games_date']),
                description=desc.format(
                    num=data['number_of_games'],
                    type=" ",
                    s="s" if data['number_of_games'] > 1 else "",
                    are_or_is="are" if data['number_of_games'] > 1 else "is",
                    content=data.get('content', '')),
                colour=color)
            if mobile:
                embed.add_field(
                    name='Games',
                    value=data['mobile'],
                    inline=True)
            else:
                embed.add_field(name='Away', value=data['away'], inline=True)
                embed.add_field(name='Home', value=data['home'], inline=True)
                embed.add_field(
                    name='Status',
                    value=data['status'],
                    inline=True)

            # embed.set_footer(text=data['copyright'], icon_url=data['icon'])
            embed.set_thumbnail(url=data['thumbnail'])

        return embed

    def _save(self):
        # with open('data/sports_db.json', 'w+') as f:
        #     json.dump(self.user_db, f)
        _ = pickle.dumps(self.user_db)
        self.db.set('sports_db', _)

    def _fetch_teams(self, mode):
        if mode == "NHL":
            data = requests.get(
                "https://statsapi.web.nhl.com/api/v1/teams").json()
            data = data['teams']
            teams = {}
            for team in data:
                teams[team['abbreviation']] = team['id']
                teams[team['name']] = team['id']
            return teams
        if mode == "MLB":
            data = requests.get(
                "https://statsapi.mlb.com/api/v1/teams?sportId=1").json()
            data = data['teams']
            teams = {}
            for team in data:
                teams[team['abbreviation']] = team['id']
                teams[team['name']] = team['id']
            return teams
        if mode == "NBA":
            year = pendulum.now().year
            year -= 1
            data = requests.get(
                f"http://data.nba.net/data/10s/prod/v1/{year}/teams.json")
            data = data.json()
            data = data['league']['standard']
            teams = {}
            for team in data:
                if team['isNBAFranchise']:
                    teams[team['tricode']] = team['nickname']
                    teams[team['fullName']] = team['tricode']
            return teams


def setup(bot):
    bot.add_cog(SportsCog(bot))
