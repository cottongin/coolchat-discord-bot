import discord
from discord.ext import commands
from discord.utils import get
import typing

import requests
import pendulum

import logging
import coloredlogs
import json
import random

import re
import time
import base64
from io import BytesIO

from PIL import Image, ImageDraw, ImageFont


LOGGER = logging.getLogger(__name__)
coloredlogs.install(level='DEBUG', logger=LOGGER,
    fmt="[{asctime}] <{name}> {levelname:>8} | {message}",
    datefmt='%Y-%m-%d %H:%M:%S',
    style='{'
)


class MockCog(commands.Cog, name="Mock"):
    """Meme Plugin featuring various mocking-related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.__name__ = __name__


    @commands.command(name='caliburn', aliases=['cb', 'fire'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def caliburn(self, ctx,
                              member: typing.Optional[discord.Member] = None, *, 
                              text: str=None):
        """Makes a sPoNgEbOb TeXt (or the last message from a provided member) meme
        e.g. caliburn haha this is going to be funny
             sal @lameuser
        """

        img_path = "assets/cb.png"
        font_path = "assets/ComicNeue-Bold.ttf"

        if not member and not text:
            with open(img_path, "rb") as fh:
                f = discord.File(fh, filename=img_path.split('/')[-1])
            await ctx.send(file=f)
            return

        if member and text:
            mode = "text"
        elif member and not text:
            mode = "member"
        elif text and not member:
            mode = "text"

        if mode == "member":
            msg = await ctx.channel.history().get(author=member)
            if not msg:
                await ctx.send("I couldn't find a recent message from {}".format(
                    self._mono(member.display_name)
                ))
                return
            text = "{}: {}".format(member.display_name, msg.clean_content)

        text = self._crazyCase(text)

        image = await self._make_image(img_path, font_path, text)
        if not image:
            LOGGER.error("Something went wrong making the image")
            await ctx.send("Sorry I couldn't make an image from that.")
            return

        await ctx.send(file=image)
    
    
    @commands.command(name='browncloud', aliases=['bc', 'sal'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def browncloud(self, ctx,
                              member: typing.Optional[discord.Member] = None, *, 
                              text: str=None):
        """Makes a sPoNgEbOb TeXt (or the last message from a provided member) meme
        e.g. browncloud haha this is going to be funny
             sal @lameuser
        """

        img_path = "assets/bc.png"
        font_path = "assets/ComicNeue-Bold.ttf"

        if not member and not text:
            with open(img_path, "rb") as fh:
                f = discord.File(fh, filename=img_path.split('/')[-1])
            await ctx.send(file=f)
            return

        if member and text:
            mode = "text"
        elif member and not text:
            mode = "member"
        elif text and not member:
            mode = "text"

        if mode == "member":
            msg = await ctx.channel.history().get(author=member)
            if not msg:
                await ctx.send("I couldn't find a recent message from {}".format(
                    self._mono(member.display_name)
                ))
                return
            text = "{}: {}".format(member.display_name, msg.clean_content)

        text = self._crazyCase(text)

        image = await self._make_image(img_path, font_path, text)
        if not image:
            LOGGER.error("Something went wrong making the image")
            await ctx.send("Sorry I couldn't make an image from that.")
            return

        await ctx.send(file=image)
    
    
    @commands.command(name='katzman', aliases=['km', 'mock2'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def katzman(self, ctx,
                              member: typing.Optional[discord.Member] = None, *, 
                              text: str=None):
        """Makes a sPoNgEbOb TeXt (or the last message from a provided member) meme
        e.g. katzman haha this is going to be funny
             mock2 @lameuser
        """

        img_path = "assets/katz.png"
        font_path = "assets/ComicNeue-Bold.ttf"

        if not member and not text:
            with open(img_path, "rb") as fh:
                f = discord.File(fh, filename=img_path.split('/')[-1])
            await ctx.send(file=f)
            return

        if member and text:
            mode = "text"
        elif member and not text:
            mode = "member"
        elif text and not member:
            mode = "text"

        if mode == "member":
            msg = await ctx.channel.history().get(author=member)
            if not msg:
                await ctx.send("I couldn't find a recent message from {}".format(
                    self._mono(member.display_name)
                ))
                return
            text = "{}: {}".format(member.display_name, msg.clean_content)

        text = self._crazyCase(text)

        image = await self._make_image(img_path, font_path, text)
        if not image:
            LOGGER.error("Something went wrong making the image")
            await ctx.send("Sorry I couldn't make an image from that.")
            return

        await ctx.send(file=image)


    @commands.command(name='ps5', aliases=['mockps5'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def ps5mock(self, ctx,
                              member: typing.Optional[discord.Member] = None, *, 
                              text: str=None):
        """Makes a sPoNgEbOb TeXt (or the last message from a provided member) meme
        e.g. taffer haha this is going to be funny
             mock3 @lameuser
        """

        img_path = "assets/ps5.jpg"
        font_path = "assets/ComicNeue-Bold.ttf"

        if not member and not text:
            with open(img_path, "rb") as fh:
                f = discord.File(fh, filename=img_path.split('/')[-1])
            await ctx.send(file=f)
            return

        if member and text:
            mode = "text"
        elif member and not text:
            mode = "member"
        elif text and not member:
            mode = "text"

        if mode == "member":
            msg = await ctx.channel.history().get(author=member)
            if not msg:
                await ctx.send("I couldn't find a recent message from {}".format(
                    self._mono(member.display_name)
                ))
                return
            text = "{}: {}".format(member.display_name, msg.clean_content)

        text = self._crazyCase(text)

        image = await self._make_image(img_path, font_path, text)
        if not image:
            LOGGER.error("Something went wrong making the image")
            await ctx.send("Sorry I couldn't make an image from that.")
            return

        await ctx.send(file=image)
    
    
    @commands.command(name='taffer', aliases=['taff', 'mock3'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def taffer(self, ctx,
                              member: typing.Optional[discord.Member] = None, *, 
                              text: str=None):
        """Makes a sPoNgEbOb TeXt (or the last message from a provided member) meme
        e.g. taffer haha this is going to be funny
             mock3 @lameuser
        """

        img_path = "assets/taffer.png"
        font_path = "assets/ComicNeue-Bold.ttf"

        if not member and not text:
            with open(img_path, "rb") as fh:
                f = discord.File(fh, filename=img_path.split('/')[-1])
            await ctx.send(file=f)
            return

        if member and text:
            mode = "text"
        elif member and not text:
            mode = "member"
        elif text and not member:
            mode = "text"

        if mode == "member":
            msg = await ctx.channel.history().get(author=member)
            if not msg:
                await ctx.send("I couldn't find a recent message from {}".format(
                    self._mono(member.display_name)
                ))
                return
            text = "{}: {}".format(member.display_name, msg.clean_content)

        text = self._crazyCase(text)

        image = await self._make_image(img_path, font_path, text)
        if not image:
            LOGGER.error("Something went wrong making the image")
            await ctx.send("Sorry I couldn't make an image from that.")
            return

        await ctx.send(file=image)


    @commands.command(name='spongebob', aliases=['sb', 'mock'])
    @commands.cooldown(1, 5, commands.BucketType.user)
    async def spongebob(self, ctx,
                              member: typing.Optional[discord.Member] = None, *, 
                              text: str=None):
        """Makes a sPoNgEbOb TeXt (or the last message from a provided member) meme
        e.g. spongebob haha this is going to be funny
             mock @lameuser
        """

        img_path = "assets/spongebob.png"
        font_path = "assets/ComicNeue-Bold.ttf"

        if not member and not text:
            with open(img_path, "rb") as fh:
                f = discord.File(fh, filename=img_path.split('/')[-1])
            await ctx.send(file=f)
            return

        if member and text:
            mode = "text"
        elif member and not text:
            mode = "member"
        elif text and not member:
            mode = "text"

        if mode == "member":
            msg = await ctx.channel.history().get(author=member)
            if not msg:
                await ctx.send("I couldn't find a recent message from {}".format(
                    self._mono(member.display_name)
                ))
                return
            text = "{}: {}".format(member.display_name, msg.clean_content)

        text = self._crazyCase(text)

        image = await self._make_image(img_path, font_path, text)
        if not image:
            LOGGER.error("Something went wrong making the image")
            await ctx.send("Sorry I couldn't make an image from that.")
            return

        await ctx.send(file=image)


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

    def _crazyCase(self, text):
        # this is dumb
        weight_upper = [False, False, True]
        weight_lower = [True, True, False]
        temp = ''
        text = text.lower()
        for idx, char in enumerate(text):
            # pick first character's case random 50/50
            if idx == 0:
                pick = random.choice([True, False])
            else:
                # pick the next character weighted, based on the previous's case
                if temp[-1].isupper():
                    pick = random.choice(weight_lower)
                else:
                    pick = random.choice(weight_upper)
            # now apply our selected case
            if pick:
                temp += char.lower()
            else:
                temp += char.upper()   
        return temp

    async def _make_image(self, path, font_path, message):
        
        try:
            # try to split multi-word string in half without cutting a word in two
            if len(message.split()) > 1:

                if len(message) - len(message.split()[0]) > 0:
                    n = len(message) // 2
                else:
                    n = len(message.split()[0])
                
                if n < len(message.split()[0]):
                    n = len(message.split()[0]) 

                half1 = message[:n]
                half2 = message[n:]

                half1_space = [pos for pos, char in enumerate(half1) if char == ' ']
                if not half1_space:
                    half1_space = [pos for pos, char in enumerate(message[:n+1]) if char == ' ']
                half2_space = half2.find(' ')

                new_half1 = message[:half1_space[-1]].strip()
                new_half2 = message[half1_space[-1]:].strip()

                top_text = new_half1
                bot_text = new_half2
            else:
                top_text = ''
                bot_text = message
                
            # defaults
            shadow = 'black'
            fill = 'white'
            img = Image.open(path)
            W, H = img.size
            draw = ImageDraw.Draw(img)
            fontsize = 1
            img_fraction = 0.9
            max_size = int(img_fraction*img.size[0])
            
            # find ideal font size based on image size 
            # and length of text
            font = ImageFont.truetype(font_path, fontsize)
            if len(top_text) > len(bot_text):
                while font.getsize(top_text)[0] < img_fraction*img.size[0]:
                    # iterate until the text size is just larger than the criteria
                    fontsize += 2
                    font = ImageFont.truetype(font_path, fontsize)
            else:
                while font.getsize(bot_text)[0] < img_fraction*img.size[0]:
                    # iterate until the text size is just larger than the criteria
                    fontsize += 2
                    font = ImageFont.truetype(font_path, fontsize)
            # if we've exceed some sane values, let's reset
            if fontsize > 60:
                fontsize = 60
                font = ImageFont.truetype(font_path, fontsize)
            elif fontsize < 28:
                fontsize = 28
                font = ImageFont.truetype(font_path, fontsize)
            # get sizes and positions for actually drawing
            wt, ht = draw.textsize(top_text, font)
            wb, hb = draw.textsize(bot_text, font)
            xt = (W-wt)/2
            yt = -10
            xb = (W-wb)/2
            yb = H-70
            # TOP TEXT
            # be smarter about how we draw the text
            lines,tmp,h = self._IntelliDraw(draw,top_text,font,W)
            # draw the text, hack for shadow by drawing the text a few times
            # in black just outside of where the actual text will be
            j = 0
            for i in lines:
                wt, _ = draw.textsize(i, font)
                xt = (W-wt)/2
                yt = 5+j*h
                # shadow/outline
                draw.text((xt-3, yt-3), i, font=font, fill=shadow)
                draw.text((xt+3, yt-3), i, font=font, fill=shadow)
                draw.text((xt-3, yt+3), i, font=font, fill=shadow)
                draw.text((xt+3, yt+3), i, font=font, fill=shadow)

                draw.text((xt, yt-3), i, font=font, fill=shadow)
                draw.text((xt, yt+3), i, font=font, fill=shadow)
                draw.text((xt-3, yt), i, font=font, fill=shadow)
                draw.text((xt+3, yt), i, font=font, fill=shadow)
                # actual text
                draw.text( (xt,yt), i , font=font, fill=fill)
                j = j + 1
            # BOTTOM TEXT
            lines,tmp,h = self._IntelliDraw(draw,bot_text,font,W)
            j = 0
            for i in lines:
                wb, _ = draw.textsize(i, font)
                xb = (W-wb)/2
                yb = (H-((fontsize+10)*len(lines)))+j*h
                draw.text((xb-3, yb-3), i, font=font, fill=shadow)
                draw.text((xb+3, yb-3), i, font=font, fill=shadow)
                draw.text((xb-3, yb+3), i, font=font, fill=shadow)
                draw.text((xb+3, yb+3), i, font=font, fill=shadow)

                draw.text((xb, yb-3), i, font=font, fill=shadow)
                draw.text((xb, yb+3), i, font=font, fill=shadow)
                draw.text((xb-3, yb), i, font=font, fill=shadow)
                draw.text((xb+3, yb), i, font=font, fill=shadow)
                draw.text( (xb,yb), i , font=font, fill=fill)
                j = j + 1

            # save the image
            bytes_buffer = BytesIO()
            img.save(bytes_buffer, "png")
            bytes_buffer.seek(0)
            image = discord.File(bytes_buffer, filename="mock.png")
            
        except:
            image = None

        return image

    def _IntelliDraw(self, drawer,text,font,containerWidth):
        words = text.split()  
        lines = [] # prepare a return argument
        lines.append(words) 
        finished = False
        line = 0
        while not finished:
            thistext = lines[line]
            newline = []
            innerFinished = False
            while not innerFinished:
                if drawer.textsize(' '.join(thistext),font)[0] > containerWidth:
                    # this is the heart of the algorithm: we pop words off the current
                    # sentence until the width is ok, then in the next outer loop
                    # we move on to the next sentence. 
                    newline.insert(0,thistext.pop(-1))
                else:
                    innerFinished = True
            if len(newline) > 0:
                lines.append(newline)
                line = line + 1
            else:
                finished = True
        tmp = []        
        for i in lines:
            tmp.append( ' '.join(i) )
        lines = tmp
        (width,height) = drawer.textsize(lines[0],font)            
        return (lines,width,height)


def setup(bot):
    bot.add_cog(MockCog(bot))