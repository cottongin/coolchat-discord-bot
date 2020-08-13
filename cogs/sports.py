import discord
from discord.ext import commands
from discord.utils import get

import requests
import pendulum

import logging
import coloredlogs
import json
import random
import os
import errno
import time
import redis
import pickle


LOGGER = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class SportsCog(commands.Cog, name="Sports"):
    """Sports Plugin featuring various sports-related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__
        self.db = redis.from_url(os.environ.get("REDIS_URL"))

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
        except:
            self.user_db = {}

        self.NHL_SCOREBOARD_ENDPOINT = (
            "https://statsapi.web.nhl.com/api/v1/schedule?startDate={}&endDate={}"
            "&expand=schedule.teams,schedule.linescore,schedule.broadcasts.all,"
            "schedule.ticket,schedule.game.content.media.epg"
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

        self.NHL_TEAMS = self._fetch_teams("NHL")
        self.MLB_TEAMS = self._fetch_teams("MLB")
        self.NBA_TEAMS = self._fetch_teams("NBA")

    @commands.command(name='sports', pass_context=True)
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_all_scores(self, ctx, *, optional_input: str=None):
        """Fetches scores from all available leagues (currently NHL, MLB, and NBA)
        """
        await ctx.invoke(self.bot.get_command('nhl'), optional_input=optional_input)
        await ctx.invoke(self.bot.get_command('mlb'), optional_input=optional_input)
        await ctx.invoke(self.bot.get_command('nba'), optional_input=optional_input)


    @commands.command(name='nhl', aliases=['nhlscores', 'hockey'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_nhl_scores(self, ctx, *, optional_input: str=None):
        """Fetches NHL scores from NHL.com

        • [optional_input] can be in the form of a specific team's tricode 
            or a date, or both
        • You can add "--tz custom timezone" to return results in your timezone. 
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
                    except:
                        await ctx.send("Sorry that is an invalid timezone "
                            "(try one from https://nodatime.org/TimeZones)")
                        return
                if arg.replace("-", "").isdigit():
                    date = arg
                if len(arg.lower()) <= 3:
                    append_team = self.NHL_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(
                        user_timezone or \
                        self.default_other_tz).format("YYYY-MM-DD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(
                        user_timezone or \
                        self.default_other_tz).format("YYYY-MM-DD")
            
            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(
                    user_timezone or \
                    self.default_other_tz).format("YYYY-MM-DD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(
                    user_timezone or \
                    self.default_other_tz).format("YYYY-MM-DD")
        
        url = self.NHL_SCOREBOARD_ENDPOINT.format(date, date) + str(append_team)
        LOGGER.debug("NHL API called for: {}".format(url))

        data = requests.get(url).json()
        games = data.get('dates', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (NHL)")
            await ctx.send(
                "I couldn't find any NHL games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date
            ))
            return
        else:
            games = games[0].get('games', {})
            if not games:
                LOGGER.warn("Something went wrong possibly. (NHL)")
                await ctx.send(
                    "I couldn't find any NHL games for {team}{date}.".format(
                        team="{} on ".format(team) if team else "",
                        date=date
                ))
                return

        games_date = pendulum.parse(games[0]['gameDate']).in_tz(
            self.default_other_tz).format("MMM Do")
        number_of_games = len(games)
        types_of_games = {
            'P': ' **PLAYOFF** ',
            'R': ' Regular season ',
            'Pre': ' Pre-season ',
        }
        type_ = types_of_games.get(games[0]['gameType'], ' ')

        away = ""
        home = ""
        details = ""
        mobile_output_string = ""

        for game in games:
            away_team = game['teams']['away']['team']['teamName'] \
                if not mobile_output \
                else game['teams']['away']['team']['abbreviation']
            home_team = game['teams']['home']['team']['teamName'] \
                if not mobile_output \
                else game['teams']['home']['team']['abbreviation']
            a_team_emoji = get(ctx.guild.emojis, name="nhl_"+game['teams']['away']['team']['abbreviation'].lower())
            h_team_emoji = get(ctx.guild.emojis, name="nhl_"+game['teams']['home']['team']['abbreviation'].lower())
            if a_team_emoji:
                if "mtl" in game['teams']['away']['team']['abbreviation'].lower():
                    a_team_emoji = "💩 "
                a_team_emoji = "{} ".format(a_team_emoji)
            else:
                a_team_emoji = ""
            if h_team_emoji:
                if "mtl" in game['teams']['home']['team']['abbreviation'].lower():
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
                        self._convert_seconds(score_bug['powerPlayInfo']['situationTimeRemaining'])
                    )
                if score_bug['teams']['home'].get('powerPlay'):
                    home_team += " (**PP {}**)".format(
                        self._convert_seconds(score_bug['powerPlayInfo']['situationTimeRemaining'])
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
                    if score_bug['intermissionInfo']['intermissionTimeRemaining'] > 0:
                        time += " **INT {}**".format(
                            self._convert_seconds(score_bug['intermissionInfo']['intermissionTimeRemaining'])
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
                time = "_Final_" # if not mobile_output else "_F_"
                if game['linescore']['currentPeriod'] >= 4:
                    time = "_Final/OT_" # if not mobile_output else "_F/OT_"
                if not mobile_output:
                    status = "{} - {} {}".format(a_score, h_score, time)
                else:
                    status = "{}".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)

            else:
                try:
                    status = pendulum.parse(game['gameDate']).in_tz(timezone or user_timezone or self.default_tz).format(
                        "h:mm A zz"
                    )
                    if int(game['status']['codedGameState']) == 2:
                        # Pre-game
                        status += " [Warmup]"
                    if "AM" == pendulum.parse(game['gameDate']).in_tz(self.default_tz).format("A") and \
                       int(status.split(":")[0]) < 10: #or game['stats'].get('startTimeTBD'):
                        status = "Time TBD"
                except:
                    status = ""
                a_score = ""
                h_score = ""

            away_team = "{}{}".format(a_team_emoji, away_team)
            home_team = "{}{}".format(h_team_emoji, home_team)
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
                status += "\n"
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
            "icon":            "http://assets.stickpng.com/thumbs/5a4fbb7bda2b4f099b95da15.png",
            "thumbnail":       "http://assets.stickpng.com/thumbs/5a4fbb7bda2b4f099b95da15.png",
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
    async def do_mlb_scores(self, ctx, *, optional_input: str=None):
        """Fetches MLB scores from MLB.com

        • [optional_input] can be in the form of a specific team's tricode or a date, or both
        • You can add "--tz custom timezone" to return results in your timezone. I will remember the last custom timezone you asked for, so there is no need to add it every time.

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
                    except:
                        await ctx.send("Sorry that is an invalid timezone (try one from https://nodatime.org/TimeZones)")
                        return
                if arg.replace("-", "").isdigit():
                    date = arg
                if len(arg.lower()) <= 3:
                    append_team = self.MLB_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(user_timezone or self.default_other_tz).format("YYYY-MM-DD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(user_timezone or self.default_other_tz).format("YYYY-MM-DD")
            
            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(user_timezone or self.default_other_tz).format("YYYY-MM-DD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(user_timezone or self.default_other_tz).format("YYYY-MM-DD")
        
        url = self.MLB_SCOREBOARD_ENDPOINT.format(date) + str(append_team)
        LOGGER.debug("MLB API called for: {}".format(url))

        data = requests.get(url).json()
        games = data.get('dates', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (MLB: fetching games)")
            await ctx.send("I couldn't find any MLB games for {team}{date}.".format(
                team="{} on ".format(team) if team else "",
                date=date
            ))
            return
        else:
            games = games[0].get('games', {})
            if not games:
                LOGGER.warn("Something went wrong possibly. (MLB: fetching games)")
                await ctx.send("I couldn't find any MLB games for {team}{date}.".format(
                    team="{} on ".format(team) if team else "",
                    date=date
                ))
                return

        # MLB.com API datetime population for doubleheaders is a JOKE.
        # This hack just matches up games and manually sets the time to +5 mins
        # for easier sorting.
        for game in games:
            if game['doubleHeader'] and game['gameNumber'] == 2:
                # this game is often populated with bogus start time data,
                # e.g. "11:33pm"
                for _ in games:
                    # now iterate over the entire list again and find the matching
                    # game with the right teams but also game 1 of the doubleheader
                    if game['teams']['away']['team']['id'] == _['teams']['away']['team']['id'] or \
                       game['teams']['away']['team']['id'] == _['teams']['home']['team']['id']:
                        if _['doubleHeader'] and _['gameNumber'] == 1:
                            # finally, hack the start time and move on
                            game['gameDate'] = pendulum.parse(_['gameDate']).add(minutes=5).to_iso8601_string()
                            break
        
        # now sort everything by start time first, then put the finished games
        # at the end (or postponed ones), and the ones in progress up top.
        status_sortorder={"Live":0, "Preview":1, "Final":2}
        games.sort(key=lambda x: (x['gameDate']))
        games.sort(key=lambda x: status_sortorder[x["status"]["abstractGameState"]])

        games_date = pendulum.parse(games[0]['gameDate']).in_tz(self.default_other_tz).format('MMM Do \'YY')
        number_of_games = len(games)
        types_of_games = {
            'P': ' **PLAYOFF** ',
            'R': ' Regular season ',
            'Pre': ' Pre-season ',
        }
        type_ = types_of_games.get(games[0]['gameType'], ' ')

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

        for game in games:
            postponed = False
            away_team = game['teams']['away']['team']['teamName'] if not mobile_output else game['teams']['away']['team']['abbreviation']
            away_id = game['teams']['away']['team']['id']
            home_team = game['teams']['home']['team']['teamName'] if not mobile_output else game['teams']['home']['team']['abbreviation']
            home_id = game['teams']['home']['team']['id']
            a_team_emoji = get(ctx.guild.emojis, name="mlb_"+game['teams']['away']['team']['abbreviation'].lower())
            h_team_emoji = get(ctx.guild.emojis, name="mlb_"+game['teams']['home']['team']['abbreviation'].lower())
            if a_team_emoji:
                if "nyy" in game['teams']['away']['team']['abbreviation'].lower():
                    a_team_emoji = "💩 "
                a_team_emoji = "{} ".format(a_team_emoji)
            else:
                a_team_emoji = ""
            if h_team_emoji:
                if "nyy" in game['teams']['home']['team']['abbreviation'].lower():
                    h_team_emoji = "💩 "
                h_team_emoji = "{} ".format(h_team_emoji)
            else:
                h_team_emoji = ""
            if game['status']['abstractGameState'] == 'Live':
                if game['status']['detailedState'] == 'Warmup':
                    try:
                        status = pendulum.parse(game['gameDate']).in_tz(timezone or user_timezone or self.default_tz).format(
                            "h:mm A zz"
                        )
                        if "AM" in status:
                            status = "Time TBD"
                    except:
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
            elif game['status']['abstractGameState'] == 'Final':
                score_bug = game.get('linescore', {})
                if not score_bug:
                    status = "{}{}".format(statuses.get(game['status']['detailedState'], "UNK"),
                                           "/"+game['status'].get('reason') if game['status'].get('reason') else "")
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
                    time = "_Final_" # if not mobile_output else "_F_"
                    if game['linescore']['currentInning'] != 9:
                        time = "_Final/{}_".format(game['linescore']['currentInning']) # if not mobile_output else "_F/OT_"
                    if not mobile_output:
                        status = "{} - {} {}".format(a_score, h_score, time)
                    else:
                        status = "{}".format(time)
                        a_score = " {}".format(a_score)
                        h_score = " {}".format(h_score)
            else:
                try:
                    status = pendulum.parse(game['gameDate']).in_tz(timezone or user_timezone or self.default_tz).format(
                        "h:mm A zz"
                    )
                    if "AM" in status:
                        status = "Time TBD"
                    if game['doubleHeader'] and game['gameNumber'] == 2:
                        # whether it's from the start time hack above, or
                        # direct from MLB.com API, this data is usually bogus
                        # so let's just set it to something more relevant
                        status = "Game 2"                        
                except:
                    status = ""
                a_score = ""
                h_score = ""

            away_team = "{}{}".format(a_team_emoji, away_team)
            home_team = "{}{}".format(h_team_emoji, home_team)
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
                    status += "\n"
                    details += status
                else:
                    away_team += "\n"
                    home_team += "\n"
                    ppd_away += away_team
                    ppd_home += home_team
                    status += "\n"
                    ppd_details += status

        embed_data = {
            "league":          "MLB",
            "games_date":      games_date,
            "number_of_games": number_of_games,
            "mobile":          mobile_output_string,
            "away":            away,
            "home":            home,
            "status":          details,
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
        multi = False # flag for later on, output multiple embeds
        if mobile_output: 
            # this is the real snag, since i only use one field for mobile
            # output, it gets large when many games are scheduled
            max_length = 1024
            if len(embed_data['mobile']) > 1024:
                # we only need to do this if we're over the limit
                cur_length = 0
                lines = embed_data['mobile'].split("\n")
                tmp = ""
                for idx,line in enumerate(lines):
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
                multi = True # set our multiple embed flag to true
                embed_data = {
                    "league":          "MLB",
                    "games_date":      games_date,
                    "number_of_games": number_of_games,
                    "mobile":          tmp,
                    "away":            away,
                    "home":            home,
                    "status":          details,
                    "copyright":       data['copyright'],
                    "icon":            "https://img.cottongin.xyz/i/4tk9zpfl.png",
                    "thumbnail":       "https://img.cottongin.xyz/i/4tk9zpfl.png",
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
                    "icon":            "https://img.cottongin.xyz/i/4tk9zpfl.png",
                    "thumbnail":       "https://img.cottongin.xyz/i/4tk9zpfl.png",
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
            ppd_embed = self._build_embed(ppd_embed_data, mobile_output, 0xCD0001)

        if timezone:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['timezone'] = timezone
            self._save()

        memes = [
            "COVID19 gonna cancel this shit",
            "Rob Manfred is a joke",
            "imagine trading Mookie Betts",
            "The Astros :astros: are a bunch of cheaters",
            "FUCK THE YANKEES",
            "imagine 60 games counting as a 'full season'",
        ]

        if multi:
            await ctx.send(content='**{}**'.format(random.choice(memes)), embed=embed1)
            await ctx.send(embed=embed2)
        else:
            await ctx.send(content='**{}**'.format(random.choice(memes)), embed=embed)
        if ppd_details:
            await ctx.send(embed=ppd_embed)


    @commands.command(name='nba', aliases=['nbascores', 'basketball'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def do_nba_scores(self, ctx, *, optional_input: str=None):
        """Fetches NBA scores from NBA.com

        • [optional_input] can be in the form of a specific team's tricode or a date, or both
        • You can add "--tz custom timezone" to return results in your timezone. I will remember the last custom timezone you asked for, so there is no need to add it every time.

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
                    except:
                        await ctx.send("Sorry that is an invalid timezone (try one from https://nodatime.org/TimeZones)")
                        return
                if arg.replace("-", "").isdigit():
                    date = arg.replace("-", "")
                if len(arg.lower()) <= 3:
                    append_team = self.NBA_TEAMS.get(arg.upper()) or ""
                    team = arg.upper()
                if arg.lower() == "tomorrow":
                    date = pendulum.tomorrow().in_tz(user_timezone or self.default_other_tz).format("YYYYMMDD")
                elif arg.lower() == "yesterday":
                    date = pendulum.yesterday().in_tz(user_timezone or self.default_other_tz).format("YYYYMMDD")
            
            if optional_input.lower() == "tomorrow":
                date = pendulum.tomorrow().in_tz(user_timezone or self.default_other_tz).format("YYYYMMDD")
            elif optional_input.lower() == "yesterday":
                date = pendulum.yesterday().in_tz(user_timezone or self.default_other_tz).format("YYYYMMDD")
        
        url = self.NBA_SCOREBOARD_ENDPOINT.format(date) #+ str(append_team)
        LOGGER.debug("NBA API called for: {}".format(url))

        data = requests.get(url).json()
        games = data.get('games', {})
        if not games:
            LOGGER.warn("Something went wrong possibly. (NBA: fetching games)")
            await ctx.send("I couldn't find any NBA games for {team}{date}.".format(
                team="{} on ".format(team) if team else "",
                date=date
            ))
            return

        sortorder={2:0, 1:1, 3:2}
        games.sort(key=lambda x: sortorder[x["statusNum"]])

        games_date = pendulum.parse(games[0]['startTimeUTC']).in_tz(self.default_other_tz).format('MMM Do \'YY')
        number_of_games = len(games)
        
        away = ""
        home = ""
        details = ""
        mobile_output_string = ""

        games_found = 0
        for game in games:
            away_team = self.NBA_TEAMS[game['vTeam']['triCode']] if not mobile_output else game['vTeam']['triCode']
            home_team = self.NBA_TEAMS[game['hTeam']['triCode']] if not mobile_output else game['hTeam']['triCode']
            a_team_emoji = get(ctx.guild.emojis, name="nba_"+game['vTeam']['triCode'].lower())
            h_team_emoji = get(ctx.guild.emojis, name="nba_"+game['hTeam']['triCode'].lower())
            if a_team_emoji:
                if "lal" in game['vTeam']['triCode'].lower():
                    a_team_emoji = "💩 "
                a_team_emoji = "{} ".format(a_team_emoji)
            else:
                a_team_emoji = ""
            if h_team_emoji:
                if "lal" in game['hTeam']['triCode'].lower():
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
                time = "_Final_" # if not mobile_output else "_F_"
                if game['period']['current'] > 4:
                    time = "_Final/{}OT_".format("" if game['period']['current'] == 5 else game['period']['current'] - 4) # if not mobile_output else "_F/OT_"
                if not mobile_output:
                    status = "{} - {} {}".format(a_score, h_score, time)
                else:
                    status = "{}".format(time)
                    a_score = " {}".format(a_score)
                    h_score = " {}".format(h_score)

            else:
                try:
                    status = pendulum.parse(game['startTimeUTC']).in_tz(timezone or user_timezone or self.default_tz).format(
                        "h:mm A zz"
                    )
                    if game['isGameActivated']:
                        status += " [Warmup]"
                except:
                    status = ""
                a_score = ""
                h_score = ""

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
                        status += "\n"
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
                    status += "\n"
                    details += status
                games_found += 1

        if games_found == 0:
            await ctx.send("I couldn't find any NBA games for {team}{date}.".format(
                team="{} on ".format(team) if team else "",
                date=date
            ))
            return

        embed_data = {
            "league":          "NBA",
            "games_date":      games_date,
            "number_of_games": games_found,
            "mobile":          mobile_output_string,
            "away":            away,
            "home":            home,
            "status":          details,
            "copyright":       "",
            "icon":            "https://cdn.freebiesupply.com/images/large/2x/nba-logo-transparent.png",
            "thumbnail":       "https://cdn.freebiesupply.com/images/large/2x/nba-logo-transparent.png",
        }

        embed = self._build_embed(embed_data, mobile_output, 0x17408B)

        if timezone:
            if not self.user_db.get(member_id):
                self.user_db[member_id] = {}
            self.user_db[member_id]['timezone'] = timezone
            self._save()

        await ctx.send(embed=embed)


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
                embed.add_field(name='Games', value=data['ppd_mobile'], inline=True)
            else:
                embed.add_field(name='Away', value=data['ppd'][0], inline=True)
                embed.add_field(name='Home', value=data['ppd'][1], inline=True)
                embed.add_field(name='Status', value=data['ppd'][2], inline=True)
        elif data.get("multi"):
            embed = discord.Embed(
                # title=data['title'],
                colour=color
            )
            if mobile:
                embed.add_field(name='Games (continued)', value=data['mobile'], inline=True)
            else:
                embed.add_field(name='Away', value=data['away'], inline=True)
                embed.add_field(name='Home', value=data['home'], inline=True)
                embed.add_field(name='Status', value=data['status'], inline=True)
        else:
            embed = discord.Embed(title='{league} Scores for {date}'.format(
                                        league=data['league'], 
                                        date=data['games_date']),
                                description='{num}{type}game{s} {are_or_is} scheduled'.format(
                                    num=data['number_of_games'],
                                    type=" ",
                                    s="s" if data['number_of_games'] > 1 else "",
                                    are_or_is="are" if data['number_of_games'] > 1 else "is"),
                                colour=color)
            if mobile:
                embed.add_field(name='Games', value=data['mobile'], inline=True)
            else:
                embed.add_field(name='Away', value=data['away'], inline=True)
                embed.add_field(name='Home', value=data['home'], inline=True)
                embed.add_field(name='Status', value=data['status'], inline=True)


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
            data = requests.get("https://statsapi.web.nhl.com/api/v1/teams").json()
            data = data['teams']
            teams = {}
            for team in data:
                teams[team['abbreviation']] = team['id']
            return teams
        if mode == "MLB":
            data = requests.get("https://statsapi.mlb.com/api/v1/teams?sportId=1").json()
            data = data['teams']
            teams = {}
            for team in data:
                teams[team['abbreviation']] = team['id']
            return teams
        if mode == "NBA":
            year = pendulum.now().year
            year -= 1
            data = requests.get(f"http://data.nba.net/data/10s/prod/v1/{year}/teams.json").json()
            data = data['league']['standard']
            teams = {}
            for team in data:
                if team['isNBAFranchise']:
                    teams[team['tricode']] = team['nickname']
            return teams


def setup(bot):
    bot.add_cog(SportsCog(bot))