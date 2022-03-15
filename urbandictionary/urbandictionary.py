from typing import Literal
import typing

import discord
import udpy

from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

PREV_DEFINITION_EMOJI = '⬅️'
NEXT_DEFINITION_EMOJI = '➡️'
URBAN_DICTIONARY_THUMBNAIL = "http://puppy-bot.com/puppy-bot-discord/media/random/urbandictionary.png"


class UrbanDictionary(commands.Cog):
    """
    Looks up definitions on urban dictionary.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.client = udpy.UrbanClient()
        self.currentLookup : typing.List[udpy.UrbanDefinition] = []
        self.currentIndex : int = 0
        self.currentMessage : discord.Message = None

    def get_embed(self):
        definition = self.currentLookup[self.currentIndex]
        embed = discord.Embed(
            title=definition.word,
            description=definition.definition,
            footer=f""
        )
        embed.set_thumbnail(url=URBAN_DICTIONARY_THUMBNAIL)
        embed.add_field(name="Example:", value=definition.example, inline=True)
        embed.set_footer(text=f"{self.currentIndex + 1}/{len(self.currentLookup)}       👍 {definition.upvotes} | 👎 {definition.downvotes}")
        return embed
        pass
    
    async def get_prev_definition(self):
        self.currentIndex -= 1
        if self.currentIndex < 0:
            self.currentIndex = len(self.currentLookup) - 1
        await self.currentMessage.edit(embed=self.get_embed())
        pass

    async def get_next_definition(self):
        self.currentIndex += 1
        if self.currentIndex >= len(self.currentLookup):
            self.currentIndex = 0
        await self.currentMessage.edit(embed=self.get_embed())
        pass

    @commands.command(usage="<term>", aliases=["ud", "urbandict"])
    async def urbandictionary(self, ctx: commands.Context, term):
        self.currentLookup : typing.List[udpy.UrbanDefinition] = self.client.get_definition(term)
        self.currentIndex = 0
        self.currentMessage : discord.Message = await ctx.channel.send(embed=self.get_embed())
        await self.currentMessage.add_reaction(PREV_DEFINITION_EMOJI)
        await self.currentMessage.add_reaction(NEXT_DEFINITION_EMOJI)
        pass
    
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction : discord.Reaction, user : discord.User):
        if user.bot == True:
            return
        if self.currentMessage == None:
            return
        if reaction.message.id != self.currentMessage.id:
            return

        await reaction.remove(user)
        
        if reaction.emoji == PREV_DEFINITION_EMOJI:
            await self.get_prev_definition()
            pass
        if reaction.emoji == NEXT_DEFINITION_EMOJI:
            await self.get_next_definition()
            pass

        pass