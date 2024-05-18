from abc import ABC
import abc
from contextlib import suppress
import inspect
import logging
import typing
import discord
from redbot.core.bot import Red
from redbot.core import commands, app_commands
from enum import auto, IntFlag
import d20

from redbot.core.commands.context import Context
from redbot.core.config import Config

from trigger.config import COG_IDENTIFIER, ReactConfig, ReactType
from trigger.embed import ReactConfigurationEmbed
from trigger.views import _EditReactView, EditReactEmbedView, EditReactGeneralView, EditReactTriggerView, EditReactResponsesView, EditReactOtherView


DefaultConfig: ReactConfig = {
    "enabled": True,
    "name": "",
    "cooldown": {"mins": "1d30", "next": 0, "last_timestamp": 0},
    "trigger": {"type": ReactType.MESSAGE, "chance": 1.0, "list": []},
    "responses": [],
    "embed": {
        "use_embed": False,
        "title": None,
        "footer": None,
        "image_url": None,
        "color": discord.Color.lighter_grey().to_rgb(),
    },
    "always_list": [],
    "channel_ids": [],
}

DEFAULT_GUILD = {
    "enabled": True,
    "reacts": {},
}

class Trigger(commands.Cog):
    """
    Controls trigger functionality and different custom triggered messages.
    """

    def __init__(self, bot: Red):
        self.bot = bot

        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        self.config.register_guild(**DEFAULT_GUILD)

    @commands.group()
    @commands.guild_only()
    @commands.mod_or_can_manage_channel()
    async def trigger(self, ctx: commands.GuildContext):
        """Manages custom triggers for reactions."""

    @trigger.command()
    @commands.is_owner()
    async def clear_all(self, ctx: commands.GuildContext, verbose: bool = True):
        """Clears all data. WARNING: Irreversible.

        Args:
            verbose (bool, optional): Verbose output. Defaults to True.
        """
        guild: discord.Guild = ctx.guild
        await self.config.guild(guild).clear()
        if verbose:
            await ctx.send(f"Data cleared for {guild.name}.")

    @trigger.command(aliases=["remove"])
    @commands.mod_or_can_manage_channel()
    async def delete(
        self,
        ctx: commands.GuildContext,
        name: typing.Annotated[str, lambda s: s.lower()],
    ):
        """Deletes a react trigger that already exists.

        Args:
            name (str): The name of the trigger.
        """
        name = name.lower()
        reacts: typing.Dict[str, ReactConfig] = await self.config.guild(
            ctx.guild
        ).reacts()

        if name not in reacts:
            await ctx.reply(f"The trigger ``{name}`` was not found.")
            return

        reacts.pop(name)

        await self.config.guild(ctx.guild).reacts.set(reacts)

        await ctx.reply(f"Deleted the trigger ``{name}``.")
        pass

    @trigger.command(aliases=["add", "new"])
    @app_commands.describe(
        type="Must be one or more of: " + ", ".join(ReactType._member_names_)
    )
    @commands.mod_or_can_manage_channel()
    async def create(
        self,
        ctx: commands.GuildContext,
        name: typing.Annotated[str, lambda s: s.lower()],
    ):
        """Creates a new react trigger based on the given react type."

        Args:
            name (str): Name for the trigger
            type (ReactType): The type of reaction.
        """
        name = name.lower()
        reacts = await self.config.guild(ctx.guild).reacts()

        if name in reacts:
            await ctx.reply(f"The trigger ``{name}`` already exists.")
            return

        config: ReactConfig = DefaultConfig
        config["name"] = name

        reacts[name] = config

        embed_message = await ctx.send("Configure the trigger below:", embed=ReactConfigurationEmbed(ctx.bot, config))

        class MessageViewObject(typing.TypedDict):
            view: typing.Optional[_EditReactView]
            message: discord.Message

        messages : typing.Dict[str, MessageViewObject] = {
            "embed": {
                "view": None,
                "message": embed_message,
            },
            "general": {
                "view": EditReactGeneralView(config, embed_message),
                "message": None,
            },
            "trigger": {
                "view": EditReactTriggerView(config, embed_message),
                "message": None,
            },
            "responses": {
                "view": EditReactResponsesView(config, embed_message),
                "message": None,
            },
            "embed": {
                "view": EditReactEmbedView(config, embed_message),
                "message": None,
            },
            "other": {
                "view": EditReactOtherView(config, embed_message),
                "message": None,
            },
        }

        messages["general"]["message"] = await ctx.send(view=messages["general"]["view"])
        messages["trigger"]["message"] = await ctx.send(content="**Trigger Type**:", view=messages["trigger"]["view"])
        messages["responses"]["message"] = await ctx.send(view=messages["responses"]["view"])
        messages["embed"]["message"] = await ctx.send(content="**Using RichEmbed Responses**:", view=messages["embed"]["view"])
        messages["other"]["message"] = await ctx.send(view=messages["other"]["view"])

        assert messages["other"]["view"] is not None

        await messages["other"]["view"].wait()

        reacts[name] = config

        await self.config.guild(ctx.guild).reacts.set(reacts)

        await ctx.reply(f"Created a new trigger under ``{name}``.")

        pass

    @trigger.command()
    @commands.mod_or_can_manage_channel()
    async def list(self, ctx: commands.GuildContext):
        """Lists all triggers for the guild."""
        reacts = await self.config.guild(ctx.guild).reacts()

        if not reacts:
            await ctx.reply("No triggers found.")
            return

        msg = ""

        for k, v in reacts.items():
            msg += f"**{k}**\n"
            msg += f"```yaml\n{v}\n```"

        await ctx.reply(msg)
