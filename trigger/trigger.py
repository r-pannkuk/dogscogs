from abc import ABC
import abc
from contextlib import suppress
import copy
from dataclasses import MISSING
import datetime
import inspect
import logging
import random
import re
import typing
import discord
import pytz
from redbot.core.bot import Red
from redbot.core import commands, app_commands
from enum import UNIQUE, StrEnum, auto, IntFlag, verify
import d20

from redbot.core.commands.context import Context
from redbot.core.config import Config

from trigger.config import COG_IDENTIFIER, ReactConfig, ReactType
from trigger.embed import ReactConfigurationEmbed, ReactEmbed
from trigger.views import _EditReactView, EditReactEmbedView, EditReactGeneralView, EditReactTriggerView, EditReactResponsesView, EditReactOtherView, ReactConfigList

@verify(UNIQUE)
class Token(StrEnum):
    MemberName = "$MEMBER_NAME$"
    ServerName = "$SERVER_NAME$"
    MemberCount = "$MEMBER_COUNT$"
    Action = "$ACTION$"
    InstigatorName = "$INSTIGATOR_NAME$"
    Context = "$CONTEXT$"

ActionType = typing.Literal["joined", "was banned", "was kicked", "left"]

class MessageOptions(typing.TypedDict, total=False):
    content: typing.Optional[str]
    embed: typing.Optional[discord.Embed]

def replace_tokens(
    text: str,
    *,
    member: typing.Optional[discord.Member] = None,
    guild: typing.Optional[discord.Guild] = None,
    action: typing.Optional[ActionType] = None,
    instigator: typing.Optional[discord.Member] = None,
    context: typing.Optional[str] = None,
    use_mentions: typing.Optional[bool] = False,
):
    if member is not None:
        text = text.replace(
                Token.MemberName.value,
                member.display_name if not use_mentions else member.mention,
            )
    if guild is not None:
        text = text.replace(Token.ServerName.value, guild.name)
        text = text.replace(Token.MemberCount.value, str(guild.member_count))
    if action is not None:
        text = text.replace(Token.Action.value, action)
    if instigator is not None:
        text = text.replace(
            Token.InstigatorName.value,
            instigator.display_name if not use_mentions else instigator.mention,
        )
    if context is not None:
        text = text.replace(Token.Context.value, context)

    return text


async def get_audit_log_reason(
    guild: discord.Guild,
    target: typing.Union[discord.abc.GuildChannel, discord.Member, discord.Role],
    action: discord.AuditLogAction,
) -> typing.Tuple[typing.Optional[discord.abc.User], typing.Optional[str]]:
    perp = None
    reason = None
    if guild.me.guild_permissions.view_audit_log:
        async for log in guild.audit_logs(limit=5, action=action):
            if log.target and log.target.id == target.id and (
                log.created_at
                > (datetime.datetime.now(tz=pytz.timezone("UTC")) - datetime.timedelta(0, 5))
            ):
                perp = log.user
                if log.reason:
                    reason = log.reason
                break
    return perp, reason



DefaultConfig: ReactConfig = {
    "enabled": True,
    "name": "",
    "cooldown": {"mins": "1d30", "next": 0, "last_timestamp": 0},
    "trigger": {"type": ReactType.MESSAGE, "chance": "100%", "list": []},
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

    async def _edit(self, ctx: commands.GuildContext, config: ReactConfig):
        """Edit a trigger configuration.

        Args:
            ctx (commands.GuildContext): Command context.
            config (ReactConfig): Configuration to edit.
        """
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
                "view": EditReactGeneralView(ctx.author, config, embed_message),
                "message": None,
            },
            "trigger": {
                "view": EditReactTriggerView(ctx.author, config, embed_message),
                "message": None,
            },
            "responses": {
                "view": EditReactResponsesView(ctx.author, config, embed_message),
                "message": None,
            },
            "embed": {
                "view": EditReactEmbedView(ctx.author, config, embed_message),
                "message": None,
            },
            "other": {
                "view": EditReactOtherView(ctx.author, config, embed_message),
                "message": None,
            },
        }

        messages["general"]["message"] = await ctx.send(view=messages["general"]["view"])
        messages["trigger"]["message"] = await ctx.send(content="**Trigger Type**:", view=messages["trigger"]["view"])
        messages["responses"]["message"] = await ctx.send(view=messages["responses"]["view"])
        messages["embed"]["message"] = await ctx.send(content="**Response Type**:", view=messages["embed"]["view"])
        messages["other"]["message"] = await ctx.send(view=messages["other"]["view"])

        assert messages["other"]["view"] is not None

        old_cooldown = config["cooldown"]["mins"]

        await messages["other"]["view"].wait()

        if config["cooldown"]["mins"] != old_cooldown:
            config["cooldown"]["next"] = 0

        reacts = await self.config.guild(ctx.guild).reacts()

        reacts[config["name"]] = config 

        await self.config.guild(ctx.guild).reacts.set(reacts)

        await ctx.channel.delete_messages([x["message"] for x in messages.values() if x["message"] is not None])

        await ctx.reply(f"Set trigger ``{config['name']}``.")


    async def _delete(self, ctx: commands.GuildContext, config: ReactConfig):
        """Delete a trigger configuration.

        Args:
            ctx (commands.GuildContext): Command context.
            config (ReactConfig): Configuration to delete.
        """
        reacts = await self.config.guild(ctx.guild).reacts()
        name = config["name"]
        reacts.pop(name)
        await self.config.guild(ctx.guild).reacts.set(reacts)

    def _generate(
            self, 
            *, 
            config: ReactConfig, 
            member: discord.Member, 
            action: typing.Optional[ActionType] = None, 
            instigator: typing.Optional[discord.Member] = None,
            context: typing.Optional[str] = None
        ) -> MessageOptions:
        """Generate a trigger based on the provided configuration.

        Args:
            ctx (commands.GuildContext): Command context.
            config (ReactConfig): Configuration to generate.
            user (typing.Union[discord.User, discord.Member]): User to generate for.
        """
        config_copy = copy.deepcopy(config)

        if config_copy["responses"] is None or len(config_copy["responses"]) == 0:
            config_copy["responses"] = ["<No Response>"]
        
        config_copy["responses"] = [replace_tokens(random.choice([x for x in config_copy["responses"]]), member=member, guild=member.guild, action=action, context=context, instigator=instigator, use_mentions=True)]

        if config_copy["embed"] is not None and config["embed"]["use_embed"]:
            if config_copy["embed"]["title"] is not None:
                config_copy["embed"]["title"] = replace_tokens(config_copy["embed"]["title"], member=member, guild=member.guild, action=action, context=context, instigator=instigator)
            if config_copy["embed"]["footer"] is not None:
                config_copy["embed"]["footer"] = replace_tokens(config_copy["embed"]["footer"], member=member, guild=member.guild, action=action, context=context, instigator=instigator)
            return {"embed": ReactEmbed(config_copy)}
        else:
            return {"content": config_copy["responses"][0]}

    async def _template(self, ctx: commands.GuildContext, config: ReactConfig) -> discord.Message:
        """Template a trigger configuration.

        Args:
            ctx (commands.GuildContext): Command context.
            config (ReactConfig): Configuration to template.
        """
        view = discord.ui.View()

        class DeleteButton(discord.ui.Button):
            async def callback(self, interaction: discord.Interaction):
                if interaction.user == ctx.author:
                    if interaction.message is not None:
                        await interaction.message.delete()

        view.add_item(DeleteButton(label="Delete", style=discord.ButtonStyle.danger, custom_id="delete_button"))

        message_content = self._generate(config=config, member=ctx.author, action="<Action>", instigator=ctx.author, context="<Context>")

        return await ctx.reply(**message_content, view=view, delete_after=60)


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

        await self._delete(ctx, reacts[name])

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
        *,
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

        await self._edit(ctx, config)

        pass

    @trigger.command()
    @commands.mod_or_can_manage_channel()
    async def list(self, ctx: commands.GuildContext):
        """Lists all triggers for the guild."""
        message = await ctx.reply("Loading...")

        while(True):
            reacts = await self.config.guild(ctx.guild).reacts()
            view = ReactConfigList(ctx.author, reacts, message)

            if not reacts or len(reacts.keys()) == 0:
                await message.edit(content="No triggers found.", embed=None, view=view)
            else:
                await message.edit(content= "", embed=ReactConfigurationEmbed(ctx.bot, reacts[next(iter(reacts))]), view=view)

            await view.wait()

            print(view.selected_config)
            print(view.action)

            if view.action == "REMOVE":
                if view.selected_config is None:
                    await ctx.reply("No valid trigger to remove.", delete_after=5)
                    continue
                await self._delete(ctx, reacts[view.selected_config])
                reacts = await self.config.guild(ctx.guild).reacts()
                await ctx.reply(f"Deleted trigger ``{view.selected_config}``.", delete_after=5)
                continue

            if view.action == "ADD":
                await message.delete()
                new_config = DefaultConfig
                new_config["name"] = "new_trigger"
                await self._edit(ctx, new_config)
                reacts = await self.config.guild(ctx.guild).reacts()
                break

            if view.action == "EDIT":
                if view.selected_config is None:
                    await ctx.reply("No valid trigger to edit.", delete_after=5)
                    continue
                await message.delete()
                await self._edit(ctx, reacts[view.selected_config])
                break

            if view.action == "TEMPLATE":
                if view.selected_config is None:
                    await ctx.reply("No valid trigger to template.", delete_after=5)
                    continue
                template_message = await self._template(ctx, reacts[view.selected_config])
                continue

        pass

    @trigger.command()
    @commands.mod_or_can_manage_channel()
    async def tokens(self, ctx: commands.GuildContext):
        """Lists all tokens available for use."""
        await ctx.reply(
            f"Available tokens for response messages:\n" +
            f"\t``{Token.MemberName.value}`` - Member's display name\n" +
            f"\t``{Token.ServerName.value}`` - Server name\n" +
            f"\t``{Token.MemberCount.value}`` - Server member count\n" +
            f"\t``{Token.Action.value}`` - Action taken, i.e. 'joined', 'banned', etc.\n" +
            f"\t``{Token.InstigatorName.value}`` - Name of the moderator who performed the above action.\n" +
            f"\t``{Token.Context.value}`` - Context of the action, i.e. the ban / kick reason"
        )

    async def _process_listener(
            self, 
            *,
            member: discord.Member, 
            message: typing.Optional[discord.Message] = None,
            action: typing.Optional[ActionType] = None,
            perp: typing.Optional[discord.Member] = None,
            context: typing.Optional[str] = None
        ):
        reacts = await self.config.guild(member.guild).reacts()

        for name, c in reacts.items():
            config : ReactConfig = c

            if config["enabled"]:
                if (
                    config["trigger"]["type"] & ReactType.MESSAGE and 
                    action is None and 
                    message is not None and 
                    any(x for x in config["trigger"]["list"] if re.match(x, message.content.lower()))
                ) or \
                config["trigger"]["type"] & ReactType.JOIN and action == "joined" or \
                config["trigger"]["type"] & ReactType.LEAVE and action == "left" or \
                config["trigger"]["type"] & ReactType.BAN and action == "was banned" or \
                config["trigger"]["type"] & ReactType.KICK and action == "was kicked":
                    chance = str(config["trigger"]["chance"])
                    if chance.find("%") != -1:
                        chance = chance.replace("%", "")
                        chance = chance[:-2] + "." + chance[-2:]
                    if (
                        member.id in config["always_list"] or
                        random.random() < d20.roll(str(chance)).total
                     ) and datetime.datetime.now(tz=pytz.timezone("UTC")).timestamp() > config["cooldown"]["next"]:
                        message_contents = self._generate(
                            config=config, 
                            member=member, 
                            action=action, 
                            instigator=perp, 
                            context=context
                        )
                        if message is not None:
                            if message.channel is not None and (
                                len(config["channel_ids"]) == 0 or
                                str(message.channel.id) in [str(id) for id in config["channel_ids"]]
                            ):
                                await message.channel.send(**message_contents)
                            else: 
                                continue
                        else:
                            for id in config["channel_ids"]:
                                channel = member.guild.get_channel(int(id))
                                if channel is not None and isinstance(channel, discord.TextChannel):
                                    await channel.send(**message_contents)

                        config["cooldown"]["last_timestamp"] = int(datetime.datetime.now(tz=pytz.timezone("UTC")).timestamp())
                        config["cooldown"]["next"] = int((
                            datetime.datetime.fromtimestamp(config["cooldown"]["last_timestamp"])
                            + datetime.timedelta(minutes=d20.roll(config["cooldown"]["mins"]).total)
                        ).timestamp())

                        reacts[name] = config

        await self.config.guild(member.guild).reacts.set(reacts)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Fires greeting messages if enabled.

        __Args__:
            member (discord.Member): Affected member.
        """
        await self._process_listener(member=member, action="joined")
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Fires departure or kick / ban messages if enabled.

        __Args__:
            member (discord.Member): Affected member.
        """

        action : ActionType

        if member.guild.me.guild_permissions.view_audit_log:
            perp, context = await get_audit_log_reason(member.guild, member, discord.AuditLogAction.kick)
            if perp is not None:
                action = "was kicked"
            else:
                perp, context = await get_audit_log_reason(member.guild, member, discord.AuditLogAction.ban)
                if perp is not None:
                    action = "was banned"
                else:
                    action = "left"
                    perp = None
                    context = None
        else:
            action = "left"
            perp = None
            context = None

        await self._process_listener(member=member, action=action, perp=member.guild.get_member(perp.id) if perp is not None else None, context=context)

        pass

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, member: discord.Member):
        """
        This is only used to track that the user was banned and not kicked/removed
        """
        pass

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, member: typing.Union[discord.Member, discord.User]):
        """
        This is only used to track that the user was banned and not kicked/removed
        """
        pass

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Listens for hello triggers and rolls a chance to trigger a response.

        Args:
            message (discord.Message): The discord message listened to.
        """
        if message.author.bot:
            return
        
        if message.author.id == self.bot.user.id:
            return
        
        if message.guild is None:
            return
        
        await self._process_listener(member=message.author, message=message)
        pass