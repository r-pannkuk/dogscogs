from contextlib import suppress
import inspect
import logging
import typing
import discord
from redbot.core.bot import Red
from redbot.core import commands, app_commands

from redbot.core.commands.context import Context
from redbot.core.config import Config


log = logging.getLogger("red")

from dogscogs_utils.cogs.reactcog import (
    ReactCog,
    GuildConfig,
    COG_IDENTIFIER,
)
from dogscogs_utils.adapters.converters import ReactType, ReactTypeConverter

from .welcomer import Welcomer
from .greeter import Greeter
from .leaver import Leaver
from .banner import Banner

DEFAULT_GUILD : typing.Mapping[str, GuildConfig] = {}


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

        self.cogs: list[ReactCog] = [
            Welcomer(bot),
            Greeter(bot),
            Leaver(bot),
            Banner(bot),
        ]

    async def dummy_lambda(self, ctx: commands.Context, *args, **kwargs):
        pass

    async def _create_cog(self, guild: discord.Guild, config: GuildConfig):
        cog = ReactCog(self.bot, config=config)

        commands.hybrid_group(name=config["name"])(self.dummy_lambda)

        self.dummy_lambda.command()(cog.clear_all)
        # group.command()(cog.enable)
        # group.command()(cog.disable)
        # group.command()(cog.enabled)
        # response = group.group(name="response")(dummy_lambda)
        # response.command(name="list")(cog.response_list)
        # response.command(name="add")(cog.response_add)
        # response.command(name="remove")(cog.response_remove)
        # channel = group.group(name="channel")(dummy_lambda)
        # channel.command(name="list")(cog.channel_list)
        # channel.command(name="add")(cog.channel_add)
        # channel.command(name="remove")(cog.channel_remove)
        # embed = group.group(name="embed")(dummy_lambda)
        # embed.command(name="enabled")(cog.embed_enabled)
        # embed.command(name="image")(cog.embed_image)
        # embed.command(name="tite")(cog.embed_title)
        # embed.command(name="footer")(cog.embed_footer)
        # group.command()(cog.template)
        # group.command()(cog.cooldown)
        # group.command()(cog.chance)
        # always = group.group(name="always")(dummy_lambda)
        # always.command(name="list")(cog.always_list)
        # always.command(name="add")(cog.always_add)
        # always.command(name="remove")(cog.always_remove)
        # triggers = group.group(name="triggers")(dummy_lambda)
        # triggers.command(name="list")(cog.trigger_list)
        # triggers.command(name="add")(cog.trigger_add)
        # triggers.command(name="remove")(cog.trigger_remove)

        await self.config.guild(guild).set_raw(config["name"], value=config)

        self.cogs.append(cog)

        return cog

    async def load_cogs(self):
        for guild in self.bot.guilds:
            guild_config = await self.config.guild(guild).all()
            mapped_names = [(await c._name(guild=guild)()).lower() for c in self.cogs]

            for key in guild_config.keys():    
                if key not in mapped_names:
                    cog = await self._create_cog(guild, guild_config[key])
                    mapped_names.append(key)
            

        for cog in self.cogs:
            if not isinstance(cog, commands.Cog):
                raise RuntimeError(
                    f"The {cog.__class__.__name__} cog in the {cog.__module__} package does "
                    f"not inherit from the commands.Cog base class. The cog author must update "
                    f"the cog to adhere to this requirement."
                )
            cog_name = cog.__cog_name__
            if cog_name in self.bot.cogs:
                await self.bot.remove_cog(cog_name)

            if not hasattr(cog, "requires"):
                commands.Cog.__init__(cog)

            added_hooks = []

            try:
                for cls in inspect.getmro(cog.__class__):
                    try:
                        hook = getattr(cog, f"_{cls.__name__}__permissions_hook")
                    except AttributeError:
                        pass
                    else:
                        self.bot.add_permissions_hook(hook)
                        added_hooks.append(hook)

                #########################################

                await cog._eject(self.bot, guild_ids=None)

                cog = await cog._inject(
                    self.bot, override=True, guild=None, guilds=None
                )

                # self.__cog_commands__ = self.__cog_commands__ + cog.__cog_commands__

                for command in cog.__cog_commands__:
                    if command.parent is None:
                        command._cog = self

                #########################################

                self.bot.dispatch("cog_add", cog)
                if "permissions" not in self.bot.extensions:
                    cog.requires.ready_event.set()
            except Exception:
                for hook in added_hooks:
                    try:
                        self.bot.remove_permissions_hook(hook)
                    except Exception:
                        # This shouldn't be possible
                        log.exception(
                            "A hook got extremely screwed up, "
                            "and could not be removed properly during another error in cog load."
                        )
                del cog
                raise

        for cls_ in getattr(self.bot, "__mro__", None) or self.bot.__class__.__mro__:
            with suppress(AttributeError):
                if hasattr(self.bot, f"_{cls_.__name__}__cogs"):
                    getattr(self.bot, f"_{cls_.__name__}__cogs")[
                        self.__cog_name__
                    ] = self
                    break

    
    @commands.hybrid_group()
    @commands.mod_or_can_manage_channel()
    async def trigger(self, ctx: commands.Context):
        """Manages custom triggers for reactions.
        """
    
    @trigger.command()
    @commands.is_owner()
    async def clear_all(
        self, ctx: commands.Context, verbose: typing.Optional[bool] = True
    ):
        """Clears all data. WARNING: Irreversible.

        Args:
            verbose (typing.Optional[bool], optional): Verbose output. Defaults to True.
        """
        guild: discord.Guild = ctx.guild
        await self.config.guild(guild).clear()
        if verbose:
            await ctx.send(f"Data cleared for {guild.name}.")

    @trigger.command(aliases=["remove"])
    @commands.mod_or_can_manage_channel()
    async def delete(self, ctx: commands.Context, name: typing.Annotated[str, lambda s: s.lower()]):
        """Deletes a react trigger that already exists.

        Args:
            name (str): The name of the trigger.
        """
        name = name.lower()
        guild_dict = await self.config.guild(ctx.guild).all()

        if name not in guild_dict:
            await ctx.reply(f"The trigger ``{name}`` was not found.")
            return
        
        try:
            cog = await anext(c for c in self.cogs if (await c._name(ctx=ctx)()).lower() == name)
        except StopAsyncIteration:
            await ctx.reply("Something went wrong.")
            return


        if cog:
            await self.bot.remove_cog(name)
        
        self.cogs.remove(cog)

        await self.config.guild(ctx.guild).clear_raw(name)

        pass

    @trigger.command()
    @app_commands.describe(type="Must be one or more of: " + ', '.join(ReactType._member_names_))
    @commands.mod_or_can_manage_channel()
    async def create(
        self,
        ctx: commands.Context,
        name: typing.Annotated[str, lambda s: s.lower()],
        *,
        type: ReactTypeConverter,
    ):
        """Creates a new react trigger based on the given react type."

        Args:
            name (str): Name for the trigger
            type (ReactType): The type of reaction.
        """
        name = name.lower()
        guild_dict = await self.config.guild(ctx.guild).all()

        if name in guild_dict:
            await ctx.reply(f"The trigger ``{name}`` already exists.")
            return

        config : GuildConfig = ReactCog.DefaultConfig
        config["name"] = name
        config["trigger"]["type"] = type

        await self._create_cog(guild=ctx.guild, config=config)

        await self.load_cogs()

        await ctx.reply(f"Created a new trigger under ``{name}``.")

        pass
