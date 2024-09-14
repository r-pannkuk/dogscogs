import copy
import datetime
import random
import re
import typing
import discord
import pytz
from redbot.core.bot import Red
from redbot.core import commands, app_commands
import d20 # type: ignore[import-untyped]
import discord_emoji # type: ignore[import-untyped]

from redbot.core.config import Config

from .config import ReactConfig, ReactType
from .embed import ReactConfigurationEmbed, ReactEmbed
from .views import _EditReactView, EditReactEmbedView, EditReactGeneralView, EditReactTriggerView, EditReactResponsesView, EditReactOtherView, EditReactUserListView, ReactConfigList

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.core import get_audit_log_reason
from dogscogs.parsers.token import Token, replace_tokens, MessageOptions, ActionType

DefaultConfig: ReactConfig = {
    "enabled": True,
    "name": "new_trigger",
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
    "never_list": [],
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

    async def load(self):
        """Load the trigger cog."""
        for guild in self.bot.guilds:
            reacts = await self.config.guild(guild).reacts()
            for name, config in reacts.items():
                config = {**DefaultConfig, **config}
                reacts[name] = config
            await self.config.guild(guild).reacts.set(reacts)
        pass

    async def _edit(self, ctx: commands.GuildContext, config: ReactConfig):
        """Edit a trigger configuration.

        Args:
            ctx (commands.GuildContext): Command context.
            config (ReactConfig): Configuration to edit.
        """
        embed_message = await ctx.send("Configure the trigger below:", embed=ReactConfigurationEmbed(ctx.bot, config))

        class MessageViewObject(typing.TypedDict):
            view: typing.Optional[_EditReactView]
            message: typing.Optional[discord.Message]

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
            "user_list": {
                "view": EditReactUserListView(ctx.author, config, embed_message),
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
        messages["user_list"]["message"] = await ctx.send(view=messages["user_list"]["view"])
        messages["responses"]["message"] = await ctx.send(view=messages["responses"]["view"])
        messages["embed"]["message"] = await ctx.send(content="**Response Type**:", view=messages["embed"]["view"])
        messages["other"]["message"] = await ctx.send(view=messages["other"]["view"])

        assert messages["other"]["view"] is not None

        old_cooldown = config["cooldown"]["mins"]

        if not await messages["other"]["view"].wait():
            if config["cooldown"]["mins"] != old_cooldown:
                config["cooldown"]["next"] = 0

            reacts = await self.config.guild(ctx.guild).reacts()

            reacts[config["name"]] = config 

            await self.config.guild(ctx.guild).reacts.set(reacts)

            await ctx.reply(f"Set trigger ``{config['name']}``.")

        await ctx.channel.delete_messages([x["message"] for x in messages.values() if x["message"] is not None])


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
            config_copy["responses"] = [""]

        responses = []
        weights = []
        param_token = r'\d+\.?\d*'
        token = re.escape(Token.WeightToken.value).replace(re.escape(Token.Param.value), param_token)

        for r in config_copy["responses"]:
            weight = re.search(token, r)

            if weight is not None:
                split_token = Token.WeightToken.value.split(Token.Param.value)
                isolated = weight.group(0).replace(split_token[0], "").replace(split_token[1], "")
                weights.append(float(isolated))
                responses.append(r.replace(weight.group(0), ""))
            else:
                weights.append(1.0)
                responses.append(r)

        choice = random.choices(
            population=responses,
            weights=weights,
        )[0]
        
        config_copy["responses"] = [replace_tokens(choice, member=member, guild=member.guild, action=action, context=context, instigator=instigator, use_mentions=True)]

        retval : MessageOptions = {
            "content": None,
            "embed": None,
            "reactions": None
        }

        param_token = r'.+?'
        token = re.escape(Token.ReactToken.value).replace(re.escape(Token.Param.value), param_token)
        found_reactions = re.search(token, config_copy["responses"][0])
        reactions = None

        if found_reactions is not None:
            split_token = Token.ReactToken.value.split(Token.Param.value)
            isolated = found_reactions.group(0).replace(split_token[0], "").replace(split_token[1], "")
            reactions = isolated.split(", ")
            config_copy["responses"][0] = config_copy["responses"][0].replace(found_reactions.group(0), "")

        if reactions is not None:
            custom_emoji_ids = [e.group(0) for e in [re.search(r"(?<=:)[\d]+(?=>)", r) for r in reactions] if e is not None]
            regular_emojis = [discord_emoji.to_unicode(discord_emoji.to_discord(r, get_all=True) or r) for r in reactions if r is not None and not any(id in r for id in custom_emoji_ids)]
            emojis = [discord.utils.get(member.guild.emojis, id=int(str(id))) for id in custom_emoji_ids if id is not None] + [r for r in regular_emojis if r is not None]
            retval["reactions"] = [e for e in emojis if e is not None]

            if len(config_copy["responses"][0]) == 0:
                config_copy["responses"][0] = None # I dunno what I'm doing here

        if config_copy["embed"] is not None and config_copy["embed"]["use_embed"]:
            if config_copy["embed"]["title"] is not None:
                config_copy["embed"]["title"] = replace_tokens(config_copy["embed"]["title"], member=member, guild=member.guild, action=action, context=context, instigator=instigator)
            if config_copy["embed"]["footer"] is not None:
                config_copy["embed"]["footer"] = replace_tokens(config_copy["embed"]["footer"], member=member, guild=member.guild, action=action, context=context, instigator=instigator)
            retval["embed"] = ReactEmbed(config_copy)
        else:
            retval["content"] = (config_copy["responses"][0] if config_copy["responses"][0] is not None else "").strip()
            retval["content"] = retval["content"] if len(retval["content"] or "") > 0 else None
        
        return retval

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

        action : typing.Optional[ActionType] = None

        if config["trigger"]["type"] & ReactType.MESSAGE:
            action = None
        if config["trigger"]["type"] & ReactType.JOIN:
            action = "joined"
        if config["trigger"]["type"] & ReactType.LEAVE:
            action = "left"
        if config["trigger"]["type"] & ReactType.KICK:
            action = "was kicked"
        if config["trigger"]["type"] & ReactType.BAN:
            action = "was banned"

        message_content = self._generate(config=config, member=ctx.author, action=action, instigator=ctx.author, context="<Context>")

        message = await ctx.reply(content=message_content["content"], embed=message_content["embed"], view=view, delete_after=60) # type: ignore[arg-type]

        for emoji in message_content["reactions"] or []:
            if isinstance(message, discord.Message):
                await message.add_reaction(emoji)
            else: 
                await ctx.message.add_reaction(emoji)

        return message


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
        reacts = await self.config.guild(ctx.guild).reacts()
        if reacts is None or len(reacts.keys()) == 0:
            await message.edit(content="No triggers found.")
            return
        selected_config : str = next(iter(reacts))

        while(True):
            reacts = await self.config.guild(ctx.guild).reacts()
            view = ReactConfigList(
                author=ctx.author, 
                reacts=reacts, 
                embed_message=message, 
                selected_config=selected_config
            )

            if not reacts or len(reacts.keys()) == 0:
                await message.edit(content="No triggers found.", embed=None, view=view)
            else:
                await message.edit(content= "", embed=ReactConfigurationEmbed(ctx.bot, reacts[selected_config]), view=view)

            await view.wait()

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
                new_config["name"] += f":{datetime.datetime.now().timestamp()}"
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
                selected_config = view.selected_config
                continue

        pass

    @trigger.command(aliases=["token"])
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
            f"\t``{Token.Context.value}`` - Context of the action, i.e. the ban / kick reason \n" +
            f"\t``{Token.ReactToken.value.replace(Token.Param.value, ':thumbsup:, :guild_emoji:, ...')}`` - React with the specified emojis\n" + 
            f"\t``{Token.WeightToken.value.replace(Token.Param.value, '3.0')}`` - Weight the response with the specified value\n" +
            "\n"
            f"Join Message Example:\n" + 
            f"``{Token.ReactToken.value.replace(Token.Param.value, ':wave:')} " + 
            f"{Token.WeightToken.value.replace(Token.Param.value, '3.0')} " + 
            f"{Token.MemberName.value} {Token.Action.value} {Token.ServerName.value}. Welcome! You are member #{Token.MemberCount.value}.``"
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

            if config["never_list"] and member.id in config["never_list"]:
                continue

            if config["enabled"]:
                if (
                    config["trigger"]["type"] & ReactType.MESSAGE and 
                    action is None and 
                    message is not None and 
                    config["trigger"]["list"] is not None and
                    any(x for x in config["trigger"]["list"] if re.match(fr"\\b{x}\\b", message.content.lower()))
                ) or \
                config["trigger"]["type"] & ReactType.JOIN and action == "joined" or \
                config["trigger"]["type"] & ReactType.LEAVE and action == "left" or \
                config["trigger"]["type"] & ReactType.BAN and action == "was banned" or \
                config["trigger"]["type"] & ReactType.KICK and action == "was kicked":
                    chance = str(config["trigger"]["chance"])
                    if chance.find("%") != -1:
                        chance = chance.replace("%", "")
                        chance = chance[:-2] + "." + chance[-2:]
                    
                    chance_result : bool = False

                    try:
                        chance_result = random.random() < float(chance)
                    except ValueError:
                        chance_result = d20.roll(str(chance)).total <= 1

                    if (
                        (
                            config["always_list"] is not None and
                            member.id in config["always_list"] 
                        ) or
                        chance_result
                     ) and datetime.datetime.now(tz=pytz.timezone("UTC")).timestamp() > config["cooldown"]["next"]:
                        message_contents = self._generate(
                            config=config, 
                            member=member, 
                            action=action, 
                            instigator=perp, 
                            context=context
                        )

                        new_message = None

                        if message_contents["content"] is not None or message_contents["embed"] is not None:
                            if message is not None:
                                if message.channel is not None and (
                                    config["channel_ids"] is None or
                                    len(config["channel_ids"]) == 0 or
                                    str(message.channel.id) in [str(id) for id in config["channel_ids"]]
                                ):
                                    new_message = await message.channel.send(content=message_contents["content"], embed=message_contents["embed"]) # type: ignore[arg-type]
                                else: 
                                    continue
                            elif config["channel_ids"] is not None:
                                for id in config["channel_ids"]:
                                    channel = member.guild.get_channel(int(id))
                                    if channel is not None and isinstance(channel, discord.TextChannel):
                                        new_message = await channel.send(content=message_contents["content"], embed=message_contents["embed"]) # type: ignore[arg-type]

                        if message_contents["reactions"] is not None:
                            if message is not None and (
                                config["channel_ids"] is None or
                                len(config["channel_ids"]) == 0 or
                                str(message.channel.id) in [str(id) for id in config["channel_ids"]]
                            ):
                                pass
                            else:
                                message = new_message
                            
                            if message is not None:
                                for emoji in message_contents["reactions"]:
                                    await message.add_reaction(emoji)

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
    @commands.guild_only()
    async def on_message(self, message: discord.Message):
        """Listens for hello triggers and rolls a chance to trigger a response.

        Args:
            message (discord.Message): The discord message listened to.
        """
        if message.author.bot:
            return
        
        if self.bot.user is None:
            return

        if message.author.id == self.bot.user.id:
            return
        
        if message.guild is None:
            return
        
        member = message.guild.get_member(message.author.id)
        
        if member is not None:
            await self._process_listener(member=member, message=message)
        pass