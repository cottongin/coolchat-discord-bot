import discord
from discord.ext import commands, tasks
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
import json
import redis
import shlex
import pickle

from re import sub
import boto3
import requests
import pendulum
# import pandas as pd
from botocore.config import Config
from requests.api import head
from warrant.aws_srp import AWSSRP


LOGGER = logging.getLogger(__name__)
coloredlogs.install(
    level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class StridekickCog(commands.Cog, name="Stridekick"):
    """shrug"""

    def __init__(self, bot):
        self._debug = False
        self.bot = bot
        self.__name__ = __name__
        # try:
        #     self.db = redis.from_url(
        #         os.environ.get("REDIS_URL"),
        #         socket_timeout=3
        #     )
        # except Exception as e:
        #     LOGGER.error(e)
        #     pass

        self.token = None
        self.expires = pendulum.now()
        self._auth.start()

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


    @tasks.loop(seconds=5)
    async def _auth(self):
        now = pendulum.now()
        if not self.token or now >= self.expires:
            print(self.expires.to_iso8601_string())
            client = boto3.client('cognito-idp', region_name='us-east-1', config=Config(signature_version="UNSIGNED"))
            aws = AWSSRP(
                username=self.bot.environs.get("STRIDEKICK_USER"),
                password=self.bot.environs.get("STRIDEKICK_PASS"),
                pool_id=self.bot.environs.get("STRIDEKICK_POOL"),
                client_id=self.bot.environs.get("STRIDEKICK_CLNT"),
                client=client,
            )
            tokens = aws.authenticate_user()
            id_token = tokens['AuthenticationResult']['IdToken']
            refresh_token = tokens['AuthenticationResult']['RefreshToken']
            access_token = tokens['AuthenticationResult']['AccessToken']
            token_type = tokens['AuthenticationResult']['TokenType']

            if tokens:
                print("Auth success")

            expires = tokens['AuthenticationResult']['ExpiresIn']
            # print(expires)
            self.token = access_token
            self.expires = now.add(seconds=int(expires))
            # print(now.add(seconds=int(expires)).to_iso8601_string())
            # self.EXPIRES = new_expires
            print(self.expires.to_iso8601_string())
        else:
            return


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

    @commands.command(name='testsk')
    async def test_stridekick(self, ctx, *, optional_input: str = None):
        """idk
        """
        for key, value in self.bot.environs.items():
            print("----\n{}: {}\n---".format(key, value))
        await ctx.send("`OK`")


    @commands.command(name='sk')
    async def stridekick(self, ctx):
        """idk"""
        base_api = "https://app.stridekick.com/graphql"

        headers = {
            'authority': 'app.stridekick.com',
            'apollographql-client-name': 'web:app',
            'app-state': 'foreground',
            'source': 'http',
            'authorization': 'Bearer {}'.format(self.token),
            'content-type': 'application/json',
            'accept': '*/*',
            'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36',
            'apollographql-client-version': '312',
            'platform': 'web',
            'sec-gpc': '1',
            'origin': 'https://app.stridekick.com',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-mode': 'cors',
            'sec-fetch-dest': 'empty',
            'accept-language': 'en-US,en;q=0.9',
        }

        payload = [
            {
                "operationName":"Friends",
                "variables":{
                    "date":"2021-05-13",
                    "search":""
                },
                "query":"query Friends($date: String, $search: String) {\n  me {\n    id\n    avatar\n    unitType\n    username\n    activity(date: $date) {\n      id\n      distance\n      minutes\n      steps\n          }\n    friends(search: $search) {\n      hits\n      members {\n        id\n        avatar\n        firstName\n        lastName\n        username\n        activity(date: $date) {\n          id\n          distance\n          minutes\n          steps\n                  }\n              }\n          }\n    memberFriends {\n      id\n          }\n      }\n}\n"
            },
            {
                "operationName":"UserStats",
                "variables":{
                    "limit":7
                },
                "query":"query UserStats($limit: Int\u0021) {\n  me {\n    id\n    lastSyncAt\n    unitType\n    client {\n      id\n      name\n      setting {\n        id\n        hasActivityOverride\n        hasManualEntry\n              }\n          }\n    activities(limit: $limit) {\n      ...MemberActivityFields\n          }\n    device {\n      id\n      provider\n          }\n    groups {\n      id\n      endDate\n      startDate\n      status\n      customActivityModules {\n        id\n              }\n      modules {\n        id\n        groupId\n        important\n              }\n          }\n      }\n}\n\nfragment MemberActivityFields on MemberActivity {\n  id\n  date\n  distance\n  minutes\n  steps\n  }\n"
            },
        ]

        data = requests.post(base_api, json=payload, headers=headers)

        active_challenge = None

        for subdata in data.json():
            d = subdata.get('data', {})
            me = d.get('me', {})
            groups = me.get('groups', [{}])
            for group in groups:
                if group.get('status', '') == 'started':
                    active_challenge = group

        print(active_challenge)

        challenge_details_query = """
        query ($groupId: Int!, $groupModuleId: Int!) {
            group(id: $groupId) {
                id
                category
                chatId
                duration
                endDate
                hex
                image
                memberCount
                startDate
                status
                title
            }
            groupModule(id: $groupModuleId) {
                id
                activityCap
                configSummary
                goal
                goalsToMeet
                groupId
                hasActivityCap
                important
                meta
                metric
                moduleName
                module {
                    name
                    title
                }
            }
        }
        """

        leaderboard_query = """
        query ($groupModuleId: Int!, $sort: Sorter, $startIndex: Int, $stopIndex: Int, $cacheTimestamp: String) {
            boom(id: $groupModuleId, cacheTimestamp: $cacheTimestamp) {
                id
                metric
                leaderboard {
                    currentUserSummary: summary {
                        ...LeaderboardFullSummaryFields
                    }
                    pagedSummaries(sort: $sort, startIndex: $startIndex, stopIndex: $stopIndex) {
                        pageInfo {
                            lastIndex
                            rowCount
                        }
                        summaries {
                            ...LeaderboardFullSummaryFields
                        }
                    }
                }
            }
        }

        fragment LeaderboardFullSummaryFields on LeaderboardSummary {
            id
            distanceAverage
            distanceTotal
            minutesAverage
            minutesTotal
            rank
            stepsAverage
            stepsTotal
            member {
                id
                avatar
                unitType
                username
            }
        }
        """

        payload = [
            {
                "operationName": None,
                "variables":{
                    "groupId": active_challenge['id'],
                    "groupModuleId": active_challenge['modules'][0]['id']
                },
                "query": challenge_details_query
            },
            {
                "operationName": None,
                "variables":{
                    "groupModuleId": active_challenge['modules'][0]['id'],
                    "startIndex":0,
                    "stopIndex":99,
                    "sort":{
                        "field":"stepsTotal",
                        "order":"desc"
                    }
                },
                "query": leaderboard_query
            }
        ]

        response = requests.post(base_api, headers=headers, json=payload)


        json_data = response.json()
        challenge = json_data[0].get('data', {})

        temp_color = int("0x{}".format(
            challenge['group']['hex'].replace("#", "")
        ), 16)
        print(temp_color)


        embed = discord.Embed(
            title=challenge['group']['title'],
            color=temp_color,
            description="{} participants · Ends {}\n".format(
                challenge['group']['memberCount'],
                challenge['group']['endDate']
            ),

        )
        embed.set_image(
            url=challenge['group']['image']
        )

        leaderboard = json_data[1].get('data', {})

        lb_list = leaderboard['boom']['leaderboard']['pagedSummaries']['summaries']
        embed.set_thumbnail(
            url=lb_list[0]['member']['avatar']
        )
        pad = 0
        step_pad = 0
        avg_pad = 0
        for entry in lb_list:
            pad = max([pad, len(entry['member']['username'])])
            avg_pad = max([avg_pad, len("{:,}".format(entry['stepsAverage']))])
            step_pad = max([step_pad, len("{:,}".format(entry['stepsTotal']))])

        embed.add_field(
            name="`Standings`",
            value="\u200b",
            inline=True
        )

        # standings = ""

        rank_map = {
            1: "🥇",
            2: "🥈",
            3: "🥉"
        }

        for entry in lb_list:
            # standings += "`{rank:>2}. {name:{pad}}\t{stepsTotal:>{step_pad},}\t{stepsAverage:>{avg_pad},}`\n".format(
            #     **entry,
            #     name=entry['member']['username'],
            #     pad=pad,
            #     step_pad=step_pad,
            #     avg_pad=avg_pad
            # )
            if len(entry['member']['username']) >= len("cottongintonic"):
                name = entry['member']['username'][:-5] + "…"
            else:
                name = entry['member']['username']
            embed.add_field(
                name="{} {}".format(rank_map.get(entry['rank'], str(entry['rank']) + "."), name).replace(" ", "\u00A0"),
                value="{stepsTotal:,} ({stepsAverage:,})".format(**entry),
                inline=True
            )
            if entry['rank'] in [1, 2]:
                embed.add_field(
                    name="\u200b",
                    value="\u200b",
                    inline=True
                )

        embed.add_field(
            name="{}. Barnabus".format(challenge['group']['memberCount'] + 1).replace(" ", "\u00A0"),
            value="0 (Fat Ass)",
            inline=True
        )

        num_fields = len(embed.fields)
        # print(num_fields)

        if num_fields % 3 == 2:
            embed.add_field(
                name="\u200b",
                value="\u200b",
                inline=True
            )


        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(StridekickCog(bot))