############################# DO NOT EDIT #############################

import asyncio
import re
import random
from datetime import datetime, timedelta
from typing import Iterable, List, Mapping, Tuple, Dict, Set, Literal, Union
import typing
from urllib.parse import quote_plus

from discord.ext.commands._types import CoroFunc
from discord.ext.commands import DynamicCooldownMapping

import discord
import rapidfuzz

from redbot.core import Config, commands
from redbot.core.commands import Parameter
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import menus, AsyncIter
from redbot.core.utils.chat_formatting import box, pagify, escape, humanize_list
from redbot.core.utils.predicates import MessagePredicate

_ = Translator("CustomCommands", __file__)

def cooldown_for_non_permitted_users(ctx: commands.Context):
    guild = ctx.guild
    if guild is not None:
        member = guild.get_member(ctx.author.id)
        if member is not None and member.guild_permissions.manage_roles:
            return None
    
    return discord.app_commands.Cooldown(
        1,                # use
        60 * 60 * 24 * 30 # per 30 days
    )

def shared_dynamic_cooldown(
    cooldown: typing.Callable[[commands.Context], typing.Optional[discord.app_commands.Cooldown]],
    type: typing.Union[commands.BucketType, typing.Callable[[commands.Context], typing.Any]],
) -> typing.Callable:
    if not callable(cooldown):
        raise TypeError("A callable must be provided")
    
    retval = DynamicCooldownMapping(cooldown, type)

    if type is commands.BucketType.default:
        raise ValueError('BucketType.default cannot be used in dynamic cooldowns')

    def decorator(func: Union[commands.Command, CoroFunc]) -> Union[commands.Command, CoroFunc]:
        if isinstance(func, commands.Command):
            func._buckets = retval # type: ignore[assignment]
        else:
            func.__commands_cooldown__ = retval # type: ignore[attr-defined]
        return func

    return decorator  # type: ignore

shared_cooldown = shared_dynamic_cooldown(cooldown_for_non_permitted_users, commands.BucketType.user)

class CCError(Exception):
    pass


class AlreadyExists(CCError):
    pass


class ArgParseError(CCError):
    pass


class NotFound(CCError):
    pass


class OnCooldown(CCError):
    pass


class CommandNotEdited(CCError):
    pass


class ResponseTooLong(CCError):
    pass


#######################################################################

class InvalidPermissions(CCError):
    pass

############################# DO NOT EDIT #############################

class CommandObj:
    def __init__(self, **kwargs):
        self.config = kwargs.get("config")
        self.bot = kwargs.get("bot")
        self.db = self.config.guild

    @staticmethod
    async def get_commands(config) -> dict:
        _commands = await config.commands()
        return {k: v for k, v in _commands.items() if _commands[k]}

    async def redact_author_ids(self, user_id: int):
        all_guilds = await self.config.all_guilds()

        for guild_id in all_guilds.keys():
            await asyncio.sleep(0)
            async with self.config.guild_from_id(guild_id).commands() as all_commands:
                async for com_name, com_info in AsyncIter(all_commands.items(), steps=100):
                    if not com_info:
                        continue

                    if com_info.get("author", {}).get("id", 0) == user_id:
                        com_info["author"]["id"] = 0xDE1
                        com_info["author"]["name"] = "Deleted User"

                    if editors := com_info.get("editors", None):
                        for index, editor_id in enumerate(editors):
                            if editor_id == user_id:
                                editors[index] = 0xDE1

    async def get_responses(self, ctx):
        intro = _(
            "Welcome to the interactive random {cc} maker!\n"
            "Every message you send will be added as one of the random "
            "responses to choose from once this {cc} is "
            "triggered. To exit this interactive menu, type `{quit}`"
        ).format(cc="customcommand", quit="exit()")
        await ctx.send(intro)

        responses = []
        args = None
        while True:
            await ctx.send(_("Add a random response:"))
            msg = await self.bot.wait_for("message", check=MessagePredicate.same_context(ctx))

            if msg.content.lower() == "exit()":
                break
            elif len(msg.content) > 2000:
                await ctx.send(
                    _(
                        "The text response you're trying to create has more than 2000 characters.\n"
                        "I cannot send messages that are longer than 2000 characters, please try again."
                    )
                )
                continue
            else:
                try:
                    this_args = ctx.cog.prepare_args(msg.content)
                except ArgParseError as e:
                    await ctx.send(e.args[0])
                    continue
                if args and args != this_args:
                    await ctx.send(_("Random responses must take the same arguments!"), delete_after=10)
                    continue
                args = args or this_args
                responses.append(msg.content)
        return responses

    @staticmethod
    def get_now() -> str:
        # Get current time as a string, for 'created_at' and 'edited_at' fields
        # in the ccinfo dict
        return "{:%d/%m/%Y %H:%M:%S}".format(datetime.utcnow())

    async def get(self, message: discord.Message, command: str) -> Tuple[str, Dict]:
        if not command:
            raise NotFound()
        ccinfo = await self.db(message.guild).commands.get_raw(command, default=None)
        blocked_channel_ids : list[str] = await self.db(message.guild).blocked_channel_ids()
        if not ccinfo:
            raise NotFound()
        if blocked_channel_ids is not None and message.channel.id in blocked_channel_ids:
            if "allow_anywhere" not in ccinfo or ccinfo["allow_anywhere"] == False:
                raise InvalidPermissions()
        return ccinfo["response"], ccinfo.get("cooldowns", {})

    async def get_full(self, message: discord.Message, command: str) -> Dict:
        ccinfo = await self.db(message.guild).commands.get_raw(command, default=None)
        if ccinfo:
            return ccinfo
        else:
            raise NotFound()

    async def create(
        self, ctx: commands.Context, command: str, *, response: Union[str, List[str]], elevated_perms: bool = False
    ):
        """Create a custom command"""
        # Check if this command is already registered as a customcommand
        if await self.db(ctx.guild).commands.get_raw(command, default=None):
            raise AlreadyExists()
        # Check against those pesky nitro users!
        if isinstance(response, str) and len(response) > 2000:
            raise ResponseTooLong()
        elif isinstance(response, list) and any([len(i) > 2000 for i in response]):
            raise ResponseTooLong()
        # test to raise
        ctx.cog.prepare_args(response if isinstance(response, str) else response[0])
        author = ctx.message.author
        ccinfo = {
            "author": {"id": author.id, "name": str(author)},
            "command": command,
            "cooldowns": {},
            "created_at": self.get_now(),
            "editors": [],
            "response": response,
            "mod_only": elevated_perms,
            "allow_anywhere": elevated_perms
        }
        await self.db(ctx.guild).commands.set_raw(command, value=ccinfo)

    async def edit(
        self,
        ctx: commands.Context,
        command: str,
        *,
        response=None,
        cooldowns: Mapping[str, int] = None,
        ask_for: bool = True,
        mod_only: bool = False,
        allow_anywhere: bool = False
    ):
        """Edit an already existing custom command"""
        ccinfo = await self.db(ctx.guild).commands.get_raw(command, default=None)

        # Check if this command is registered
        if not ccinfo:
            raise NotFound()

        author = ctx.message.author

        if "mod_only" in ccinfo and ccinfo["mod_only"]:
            if not author.guild_permissions.moderate_members:
                raise InvalidPermissions()

        if ask_for and not response:
            await ctx.send(_("Do you want to create a 'randomized' custom command?") + " (yes/no)")

            pred = MessagePredicate.yes_or_no(ctx)
            try:
                await self.bot.wait_for("message", check=pred, timeout=30)
            except asyncio.TimeoutError:
                await ctx.send(_("Response timed out, please try again later."), delete_after=10)
                raise CommandNotEdited()
            if pred.result is True:
                response = await self.get_responses(ctx=ctx)
            else:
                prev_response = ccinfo["response"]
                prompt = "What response do you want?"

                if prev_response:
                    if isinstance(prev_response, list):
                        prompt += f"\n\nPrevious responses:\n{humanize_list(prev_response)}"
                    else:
                        prompt += f"\n\nPrevious response:\n{prev_response}"
                await ctx.send(_(prompt))
                try:
                    resp = await self.bot.wait_for(
                        "message", check=MessagePredicate.same_context(ctx), timeout=180
                    )
                except asyncio.TimeoutError:
                    await ctx.send(_("Response timed out, please try again later."), delete_after=10)
                    raise CommandNotEdited()
                response = resp.content

            if author.guild_permissions.moderate_members:
                await ctx.send(_("Do you want to restrict editing this command to mods only?") + " (yes/no)")

                pred = MessagePredicate.yes_or_no(ctx)
                try:
                    await self.bot.wait_for("message", check=pred, timeout=30)
                except asyncio.TimeoutError:
                    await ctx.send(_("Response timed out, please try again later."), delete_after=10)
                    raise CommandNotEdited()
                mod_only = pred.result

                await ctx.send(_("Do you want to allow this command to be used anywhere?") + " (yes/no)")

                pred = MessagePredicate.yes_or_no(ctx)
                try:
                    await self.bot.wait_for("message", check=pred, timeout=30)
                except asyncio.TimeoutError:
                    await ctx.send(_("Response timed out, please try again later."), delete_after=10)
                    raise CommandNotEdited()
                allow_anywhere = pred.result


        if response:
            # test to raise
            if len(response) > 2000:
                raise ResponseTooLong()
            ctx.cog.prepare_args(response if isinstance(response, str) else response[0])
            ccinfo["response"] = response

        if cooldowns:
            ccinfo.setdefault("cooldowns", {}).update(cooldowns)
            for key, value in ccinfo["cooldowns"].copy().items():
                if value <= 0:
                    del ccinfo["cooldowns"][key]

        if author.id not in ccinfo["editors"]:
            # Add the person who invoked the `edit` coroutine to the list of
            # editors, if the person is not yet in there
            ccinfo["editors"].append(author.id)

        if mod_only is not None:
            # Allows only mods to edit this.
            ccinfo["mod_only"] = mod_only

        if allow_anywhere is not None:
            # Allows anyone to use this command anywhere.
            ccinfo["allow_anywhere"] = allow_anywhere

        ccinfo["edited_at"] = self.get_now()

        await self.db(ctx.guild).commands.set_raw(command, value=ccinfo)

    async def delete(self, ctx: commands.Context, command: str):
        """Delete an already existing custom command"""
        # Check if this command is registered
        if not await self.db(ctx.guild).commands.get_raw(command, default=None):
            raise NotFound()
        
        ccinfo = await self.db(ctx.guild).commands.get_raw(command, default=None)

        if "mod_only" in ccinfo and ccinfo["mod_only"]:
            if not ctx.author.guild_permissions.moderate_members:
                raise InvalidPermissions()

        await self.db(ctx.guild).commands.set_raw(command, value=None)

#######################################################################

@cog_i18n(_)
class ModCustomCommands(commands.Cog):
    """This cog contains commands for creating and managing custom commands that display text.

    These are useful for storing information members might need, like FAQ answers or invite links.
    Custom commands can be used by anyone by default, so be careful with pings.
    Commands can only be lowercase, and will not respond to any uppercase letters.

    Note: This cog will ADD TO and EDIT the existing CustomCom config.
    """

    def __init__(self, bot):
        super().__init__()
        self.bot = bot
        self.key = 414589031223512
        self.config = Config.get_conf(None, self.key, cog_name="CustomCommands")
        self.config.register_guild(commands={})
        self.commandobj = CommandObj(config=self.config, bot=self.bot)
        self.cooldowns = {}

    async def _list(self, ctx: commands.Context, cc_dict: dict):
        results = self.prepare_command_list(ctx, sorted(cc_dict.items(), key=lambda t: t[0]))

        if await ctx.embed_requested():
            # We need a space before the newline incase the CC preview ends in link (GH-2295)
            content = " \n".join(map("**{0[0]}** {0[1]}".format, results))
            pages = list(pagify(content, page_length=1024))
            embed_pages = []
            for idx, page in enumerate(pages, start=1):
                embed = discord.Embed(
                    title=_("Custom Command List"),
                    description=page,
                    colour=await ctx.embed_colour(),
                )
                embed.set_footer(text=_("Page {num}/{total}").format(num=idx, total=len(pages)))
                embed_pages.append(embed)
            await menus.menu(ctx, embed_pages)
        else:
            content = "\n".join(map("{0[0]:<12} : {0[1]}".format, results))
            pages = list(map(box, pagify(content, page_length=2000, shorten_by=10)))
            await menus.menu(ctx, pages)

############################# DO NOT EDIT #############################

    async def red_delete_data_for_user(
        self,
        *,
        requester: Literal["discord_deleted_user", "owner", "user", "user_strict"],
        user_id: int,
    ):
        if requester != "discord_deleted_user":
            return

        await self.commandobj.redact_author_ids(user_id)

    @commands.group(aliases=["cc"])
    @commands.guild_only()
    async def customcom(self, ctx: commands.Context):
        """Base command for Custom Commands management."""
        pass

    @customcom.command(name="raw")
    async def cc_raw(self, ctx: commands.Context, command: str.lower):
        """Get the raw response of a custom command, to get the proper markdown.

        This is helpful for copy and pasting.

        **Arguments:**

        - `<command>` The custom command to get the raw response of."""
        commands = await self.config.guild(ctx.guild).commands()
        if command not in commands:
            return await ctx.send("That command doesn't exist.")
        command = commands[command]
        if isinstance(command["response"], str):
            raw = discord.utils.escape_markdown(command["response"])
            if len(raw) > 2000:
                raw = f"{raw[:1997]}..."
            await ctx.send(raw)
        else:
            msglist = []
            if await ctx.embed_requested():
                colour = await ctx.embed_colour()
                for number, response in enumerate(command["response"], start=1):
                    raw = discord.utils.escape_markdown(response)
                    if len(raw) > 2048:
                        raw = f"{raw[:2045]}..."
                    embed = discord.Embed(
                        title=_("Response #{num}/{total}").format(
                            num=number, total=len(command["response"])
                        ),
                        description=raw,
                        colour=colour,
                    )
                    msglist.append(embed)
            else:
                for number, response in enumerate(command["response"], start=1):
                    raw = discord.utils.escape_markdown(response)
                    msg = _("Response #{num}/{total}:\n{raw}").format(
                        num=number, total=len(command["response"]), raw=raw
                    )
                    if len(msg) > 2000:
                        msg = f"{msg[:1997]}..."
                    msglist.append(msg)
            await menus.menu(ctx, msglist)

    @customcom.command(name="search")
    @commands.guild_only()
    async def cc_search(self, ctx: commands.Context, *, query):
        """
        Searches through custom commands, according to the query.

        Uses fuzzy searching to find close matches.

        **Arguments:**

        - `<query>` The query to search for. Can be multiple words.
        """
        cc_commands = await CommandObj.get_commands(self.config.guild(ctx.guild))
        extracted = rapidfuzz.process.extract(
            query, list(cc_commands.keys()), processor=rapidfuzz.utils.default_process
        )
        accepted = []
        for key, score, __ in extracted:
            if score > 60:
                # Match was decently strong
                accepted.append((key, cc_commands[key]))
            else:
                # Match wasn't strong enough
                pass
        if len(accepted) == 0:
            return await ctx.send(_("No close matches were found."))
        results = self.prepare_command_list(ctx, accepted)
        if await ctx.embed_requested():
            content = " \n".join(map("**{0[0]}** {0[1]}".format, results))
            embed = discord.Embed(
                title=_("Search results"), description=content, colour=await ctx.embed_colour()
            )
            await ctx.send(embed=embed)
        else:
            content = "\n".join(map("{0[0]:<12} : {0[1]}".format, results))
            await ctx.send(_("The following matches have been found:") + box(content))

    @customcom.group(name="create", aliases=["add"], invoke_without_command=True)
    @commands.mod_or_permissions(administrator=True)
    @shared_cooldown # type: ignore[arg-type]
    async def cc_create(self, ctx: commands.Context, command: str.lower, *, text: str):
        """Create custom commands.

        If a type is not specified, a simple CC will be created.
        CCs can be enhanced with arguments, see the guide
        [here](https://docs.discord.red/en/stable/cog_customcom.html).
        """
        await ctx.invoke(self.cc_create_simple, command=command, text=text)

    @cc_create.command(name="random")
    @commands.mod_or_permissions(administrator=True)
    @shared_cooldown # type: ignore[arg-type]
    async def cc_create_random(self, ctx: commands.Context, command: str.lower):
        """Create a CC where it will randomly choose a response!

        Note: This command is interactive.

        **Arguments:**

        - `<command>` The command executed to return the text. Cast to lowercase.
        """
        if any(char.isspace() for char in command):
            # Haha, nice try
            await ctx.send(_("Custom command names cannot have spaces in them."), delete_after=10)
            return
        if command in (*self.bot.all_commands, *commands.RESERVED_COMMAND_NAMES):
            await ctx.send(_("There already exists a bot command with the same name."), delete_after=10)
            return
        responses = await self.commandobj.get_responses(ctx=ctx)
        if not responses:
            await ctx.send(_("Custom command process cancelled."), delete_after=10)
            return
        try:
            await self.commandobj.create(ctx=ctx, command=command, response=responses)
            await ctx.send(_("Custom command successfully added."))
        except AlreadyExists:
            await ctx.send(
                _("This command already exists. Use `{command}` to edit it.").format(
                    command=f"{ctx.clean_prefix}customcom edit"
                )
            , delete_after=20)
        except ResponseTooLong:  # This isn't needed, however may be a good idea to keep this.
            await ctx.send(
                _(
                    "The text response you're trying to create has more than 2000 characters.\n"
                    "I cannot send messages that are longer than 2000 characters."
                )
            , delete_after=20)

    @cc_create.command(name="simple")
    @commands.mod_or_permissions(administrator=True)
    @shared_cooldown # type: ignore[arg-type]
    async def cc_create_simple(self, ctx, command: str.lower, *, text: str):
        """Add a simple custom command.

        Example:
        - `[p]customcom create simple yourcommand Text you want`

        **Arguments:**

        - `<command>` The command executed to return the text. Cast to lowercase.
        - `<text>` The text to return when executing the command. See guide for enhanced usage.
        """
        if any(char.isspace() for char in command):
            # Haha, nice try
            await ctx.send(_("Custom command names cannot have spaces in them."), delete_after=10)
            return
        if command in (*self.bot.all_commands, *commands.RESERVED_COMMAND_NAMES):
            await ctx.send(_("There already exists a bot command with the same name."), delete_after=10)
            return
        try:
            await self.commandobj.create(ctx=ctx, command=command, response=text, elevated_perms=False)
            await ctx.send(_("Custom command successfully added."))
        except AlreadyExists:
            await ctx.send(
                _("This command already exists. Use `{command}` to edit it.").format(
                    command=f"{ctx.clean_prefix}customcom edit"
                )
            , delete_after=20)
        except ArgParseError as e:
            await ctx.send(e.args[0])
        except ResponseTooLong:
            await ctx.send(
                _(
                    "The text response you're trying to create has more than 2000 characters.\n"
                    "I cannot send messages that are longer than 2000 characters."
                )
            , delete_after=20)

    @customcom.command(name="cooldown")
    @commands.mod_or_permissions(administrator=True)
    async def cc_cooldown(
        self, ctx, command: str.lower, cooldown: int = None, *, per: str.lower = "member"
    ):
        """Set, edit, or view the cooldown for a custom command.

        You may set cooldowns per member, channel, or guild. Multiple
        cooldowns may be set. All cooldowns must be cooled to call the
        custom command.

        Examples:
        - `[p]customcom cooldown pingrole`
        - `[p]customcom cooldown yourcommand 30`
        - `[p]cc cooldown mycommand 30 guild`

        **Arguments:**

        - `<command>` The custom command to check or set the cooldown.
        - `[cooldown]` The number of seconds to wait before allowing the command to be invoked again. If omitted, will instead return the current cooldown settings.
        - `[per]` The group to apply the cooldown on. Defaults to per member. Valid choices are server / guild, user / member, and channel.
        """
        if cooldown is None:
            try:
                cooldowns = (await self.commandobj.get(ctx.message, command))[1]
            except NotFound:
                return await ctx.send(_("That command doesn't exist.", delete_after=10))
            if cooldowns:
                cooldown = []
                for per, rate in cooldowns.items():
                    cooldown.append(
                        _("A {} may call this command every {} seconds").format(per, rate)
                    )
                return await ctx.send("\n".join(cooldown))
            else:
                return await ctx.send(_("This command has no cooldown."))
        per = {"server": "guild", "user": "member"}.get(per, per)
        allowed = ("guild", "member", "channel")
        if per not in allowed:
            return await ctx.send(_("{} must be one of {}").format("per", ", ".join(allowed)))
        cooldown = {per: cooldown}
        try:
            await self.commandobj.edit(ctx=ctx, command=command, cooldowns=cooldown, ask_for=False)
            await ctx.send(_("Custom command cooldown successfully edited."))
        except NotFound:
            await ctx.send(
                _("That command doesn't exist. Use `{command}` to add it.").format(
                    command=f"{ctx.clean_prefix}customcom create"
                )
            , delete_after=10)

    @customcom.command(name="delete", aliases=["del", "remove"])
    @commands.mod_or_permissions(administrator=True)
    async def cc_delete(self, ctx, command: str.lower):
        """Delete a custom command.

        Example:
        - `[p]customcom delete yourcommand`

        **Arguments:**

        - `<command>` The custom command to delete.
        """
        try:
            await self.commandobj.delete(ctx=ctx, command=command)
            await ctx.send(_("Custom command successfully deleted."))
        except NotFound:
            await ctx.send(_("That command doesn't exist."), delete_after=10)
        except InvalidPermissions:
            await ctx.send(_("You do not have permission to delete this command."), delete_after=10)

    @customcom.command(name="edit")
    @commands.mod_or_permissions(administrator=True)
    async def cc_edit(self, ctx, command: str.lower, *, text: str = None):
        """Edit a custom command.

        Example:
        - `[p]customcom edit yourcommand Text you want`

        **Arguments:**

        - `<command>` The custom command to edit.
        - `<text>` The new text to return when executing the command.
        """
        try:
            await self.commandobj.edit(ctx=ctx, command=command, response=text)
            await ctx.send(_("Custom command successfully edited."))
        except NotFound:
            await ctx.send(
                _("That command doesn't exist. Use `{command}` to add it.").format(
                    command=f"{ctx.clean_prefix}customcom create"
                )
            , delete_after=20)
        except ArgParseError as e:
            await ctx.send(e.args[0])
        except CommandNotEdited:
            pass
        except ResponseTooLong:
            await ctx.send(
                _(
                    "The text response you're trying to create has more than 2000 characters.\n"
                    "I cannot send messages that are longer than 2000 characters."
                )
            , delete_after=20)
        except InvalidPermissions:
            await ctx.send(_("You do not have permission to edit this command."), delete_after=10)

    @customcom.command(name="list")
    @commands.bot_can_react()
    async def cc_list(self, ctx: commands.Context):
        """List all available custom commands.

        The list displays a preview of each command's response, with
        markdown escaped and newlines replaced with spaces.
        """
        blocked_channel_ids : list[str] = await self.config.guild(ctx.message.guild).blocked_channel_ids()
        if blocked_channel_ids is not None and ctx.message.channel.id in blocked_channel_ids:
            await ctx.send(_("Custom commands cannot be used in this channel."), delete_after=5)
            await ctx.message.delete(delay=5)
            return

        cc_dict = await CommandObj.get_commands(self.config.guild(ctx.guild))

        cc_dict = {k: v for k, v in cc_dict.items() if not ("mod_only" in v and v["mod_only"])}
        
        if not cc_dict:
            await ctx.send(
                _(
                    "There are no custom commands in this server."
                    " Use `{command}` to start adding some."
                ).format(command=f"{ctx.clean_prefix}customcom create")
            , delete_after=10)
            return

        await self._list(ctx, cc_dict)

    @customcom.command(name="show")
    async def cc_show(self, ctx, command_name: str):
        """Shows a custom command's responses and its settings.

        **Arguments:**

        - `<command_name>` The custom command to show.
        """

        try:
            cmd = await self.commandobj.get_full(ctx.message, command_name)
        except NotFound:
            await ctx.send(_("I could not not find that custom command."), delete_after=10)
            return

        responses = cmd["response"]

        if isinstance(responses, str):
            responses = [responses]

        _aid = cmd["author"]["id"]

        if _aid == 0xDE1:
            author = _("Deleted User")
        elif member := ctx.guild.get_member(_aid):
            author = f"{member} ({_aid})"
        else:
            author = f"{cmd['author']['name']} ({_aid})"

        _type = _("Random") if len(responses) > 1 else _("Normal")

        blocked_channel_ids = await self.config.guild(ctx.guild).blocked_channel_ids()
        blocked_channel_names = [f"#{c.name}" for c in ctx.guild.channels if c.id in blocked_channel_ids] if blocked_channel_ids else []
        if len(blocked_channel_names) > 0:
            _run_permissions = _("Anywhere") if "allow_anywhere" in cmd and cmd["allow_anywhere"] else _("Anywhere but {channels}").format(channels=humanize_list(blocked_channel_names))
        else:
            _run_permissions = _("Anywhere")

        _edit_permissions = _("Author") if "mod_only" not in cmd or not cmd["mod_only"] else _("Moderators")

        text = _(
            "Command: {command_name}\n"
            "Author: {author}\n"
            "Created: {created_at}\n"
            "Type: {type}\n"
            "Permissions:\n"
            "  Can Run: {run_permissions}\n"
            "  Can Edit: {edit_permissions}\n"
        ).format(
            command_name=command_name, author=author, created_at=cmd["created_at"], type=_type, run_permissions=_run_permissions, edit_permissions=_edit_permissions
        )

        cooldowns = cmd.get("cooldowns", {})

        if cooldowns:
            cooldown_text = _("Cooldowns:\n")
            for rate, per in cooldowns.items():
                cooldown_text += _("{num} seconds per {period}\n").format(num=per, period=rate)
            text += cooldown_text

        text += _("Responses:\n")
        responses = ["- " + r for r in responses]
        text += "\n".join(responses)

        for p in pagify(text):
            await ctx.send(box(p, lang="yaml"))

#######################################################################
            
    @commands.group(aliases=["mcc"])
    @commands.guild_only()
    async def modcustomcom(self, ctx: commands.Context):
        """Base command for elevated Custom Commands management."""
        pass

    @modcustomcom.command(name="list")
    @commands.bot_can_react()
    async def mcc_list(self, ctx: commands.Context):
        """List all available elevated custom commands.

        Custom commands displayed in this list are officialized by the
        mods on the server, and have elevated permissions.
        """
        
        cc_dict = await CommandObj.get_commands(self.config.guild(ctx.guild))

        cc_dict = {k: v for k, v in cc_dict.items() if "mod_only" in v and v["mod_only"]}

        if not cc_dict:
            await ctx.send(
                _(
                    "There are no elevated custom commands in this server."
                    " Use `{create_command}` to start adding some, or `{edit_command}` to promote an existing command."
                ).format(create_command=f"{ctx.clean_prefix}modcustomcom create", edit_command=f"{ctx.clean_prefix}modcustomcom promote")
            )
            return

        await self._list(ctx, cc_dict)

    @modcustomcom.group(name="create", aliases=["add"], invoke_without_command=True)
    @commands.mod_or_permissions(moderate_members=True)
    async def mcc_create(self, ctx: commands.Context, command: str.lower, *, text: str):
        """Add a simple custom command.

        Example:
        - `[p]modcustomcom create simple yourcommand Text you want`

        **Arguments:**

        - `<command>` The command executed to return the text. Cast to lowercase.
        - `<text>` The text to return when executing the command. See guide for enhanced usage.
        """
        if any(char.isspace() for char in command):
            # Haha, nice try
            await ctx.send(_("Custom command names cannot have spaces in them."), delete_after=10)
            return
        if command in (*self.bot.all_commands, *commands.RESERVED_COMMAND_NAMES):
            await ctx.send(_("There already exists a bot command with the same name."), delete_after=10)
            return
        try:
            await self.commandobj.create(ctx=ctx, command=command, response=text, elevated_perms=True)
            await ctx.send(_("Custom command successfully added."))
        except AlreadyExists:
            await ctx.send(
                _("This command already exists. Use `{command}` to edit it.").format(
                    command=f"{ctx.clean_prefix}customcom edit"
                )
            , delete_after=20)
        except ArgParseError as e:
            await ctx.send(e.args[0], delete_after=20)
        except ResponseTooLong:
            await ctx.send(
                _(
                    "The text response you're trying to create has more than 2000 characters.\n"
                    "I cannot send messages that are longer than 2000 characters."
                )
            , delete_after=20)

    @modcustomcom.command(name="promote")
    @commands.mod_or_permissions(moderate_members=True)
    async def mcc_promote(self, ctx: commands.Context, command: str.lower):
        """Convert an existing custom command to a mod command.

        Example:
        - `[p]modcustomcom promote yourcommand`

        **Arguments:**

        - `<command>` The custom command to promote.
        """
        try:
            await self.commandobj.edit(ctx=ctx, command=command, ask_for=False, mod_only=True, allow_anywhere=True)
            await ctx.send(_("Custom command successfully promoted."), delete_after=10)
        except NotFound:
            await ctx.send(
                _("That command doesn't exist. Use `{command}` to add it.").format(
                    command=f"{ctx.clean_prefix}modcustomcom create"
                )
            , delete_after=20)
        except ArgParseError as e:
            await ctx.send(e.args[0], delete_after=10)
        except CommandNotEdited:
            pass

    @modcustomcom.group(name="default")
    @commands.mod_or_permissions(moderate_members=True)
    async def mcc_default(self, ctx: commands.Context):
        """Manage default behavior for custom commands."""
        pass

    @mcc_default.command(name="blocked")
    @commands.mod_or_permissions(moderate_members=True)
    async def mcc_blocked_channels(self, ctx: commands.Context, *channels: discord.TextChannel):
        """Set the channels where regular custom commands cannot be used.

        This will prevent custom commands from being used in the specified channels. Elevated custom commands
        will still be able to be used in these channels.

        **Arguments:**

        - `<channels>` The channels where mod commands cannot be used.
        """
        if not channels:
            blocked_channel_ids = await self.config.guild(ctx.guild).blocked_channel_ids()
            if not blocked_channel_ids:
                return await ctx.send(_("Custom commands can be used anywhere."))
            channels = [c for c in ctx.guild.channels if c.id in blocked_channel_ids]
        await self.config.guild(ctx.guild).blocked_channel_ids.set([c.id for c in channels])
        await ctx.send(_("Custom commands cannot be used in {channels}.").format(channels=humanize_list([f"{c.mention}" for c in channels])))

############################# DO NOT EDIT #############################

    @commands.Cog.listener()
    async def on_message_without_command(self, message):
        is_private = message.guild is None

        # user_allowed check, will be replaced with self.bot.user_allowed or
        # something similar once it's added
        user_allowed = True

        if isinstance(message.channel, discord.PartialMessageable):
            return

        if len(message.content) < 2 or is_private or not user_allowed or message.author.bot:
            return

        if await self.bot.cog_disabled_in_guild(self, message.guild):
            return

        ctx = await self.bot.get_context(message)

        if ctx.prefix is None:
            return

        try:
            raw_response, cooldowns = await self.commandobj.get(
                message=message, command=ctx.invoked_with
            )
            if isinstance(raw_response, list):
                raw_response = random.choice(raw_response)
            elif isinstance(raw_response, str):
                pass
            else:
                raise NotFound()
            if cooldowns:
                self.test_cooldowns(ctx, ctx.invoked_with, cooldowns)
        except InvalidPermissions:
            await ctx.send(_("Custom commands cannot be used in this channel."), delete_after=5)
            await message.delete(delay=5)
            return
        except CCError:
            return

        # wrap the command here so it won't register with the bot
        fake_cc = commands.command(name=ctx.invoked_with)(self.cc_callback)
        fake_cc.params = self.prepare_args(raw_response)
        fake_cc.requires.ready_event.set()
        ctx.command = fake_cc

        await self.bot.invoke(ctx)
        if not ctx.command_failed:
            await self.cc_command(*ctx.args, **ctx.kwargs, raw_response=raw_response)

    async def cc_callback(self, *args, **kwargs) -> None:
        """
        Custom command.

        Created via the CustomCom cog. See `[p]customcom` for more details.
        """
        # fake command to take advantage of discord.py's parsing and events
        pass

    async def cc_command(self, ctx, *cc_args, raw_response, **cc_kwargs) -> None:
        cc_args = (*cc_args, *cc_kwargs.values())
        results = re.findall(r"{([^}]+)\}", raw_response)
        for result in results:
            param = self.transform_parameter(result, ctx.message)
            raw_response = raw_response.replace("{" + result + "}", param)
        results = re.findall(r"{((\d+)[^.}]*(\.[^:}]+)?[^}]*)\}", raw_response)
        if results:
            low = min(int(result[1]) for result in results)
            for result in results:
                index = int(result[1]) - low
                arg = self.transform_arg(result[0], result[2], cc_args[index])
                raw_response = raw_response.replace("{" + result[0] + "}", arg)
        await ctx.send(raw_response)

    @staticmethod
    def prepare_args(raw_response) -> Mapping[str, Parameter]:
        args = re.findall(r"{(\d+)[^:}]*(:[^.}]*)?[^}]*\}", raw_response)
        if not args:
            return {}
        allowed_builtins = {
            "bool": bool,
            "complex": complex,
            "float": float,
            "frozenset": frozenset,
            "int": int,
            "list": list,
            "set": set,
            "str": str,
            "tuple": tuple,
            "query": quote_plus,
        }
        indices = [int(a[0]) for a in args]
        low = min(indices)
        indices = [a - low for a in indices]
        high = max(indices)
        if high > 9:
            raise ArgParseError(_("Too many arguments!"))
        gaps = set(indices).symmetric_difference(range(high + 1))
        if gaps:
            raise ArgParseError(
                _("Arguments must be sequential. Missing arguments: ")
                + ", ".join(str(i + low) for i in gaps)
            )
        fin = [Parameter("_" + str(i), Parameter.POSITIONAL_OR_KEYWORD) for i in range(high + 1)]
        for arg in args:
            index = int(arg[0]) - low
            anno_raw = arg[1][1:]  # strip initial colon
            if anno_raw.lower().endswith("converter"):
                anno_raw = anno_raw[:-9]
            if not anno_raw or anno_raw.startswith("_"):  # public types only
                name = "{}_{}".format("text", index if index < high else "final")
                fin[index] = fin[index].replace(name=name)
                continue
            # allow type hinting only for discord.py and builtin types
            try:
                anno = getattr(discord, anno_raw)
                # force an AttributeError if there's no discord.py converter
                getattr(commands, anno.__name__ + "Converter")
            except AttributeError:
                anno = allowed_builtins.get(anno_raw.lower(), Parameter.empty)
            if (
                anno is not Parameter.empty
                and fin[index].annotation is not Parameter.empty
                and anno != fin[index].annotation
            ):
                raise ArgParseError(
                    _(
                        'Conflicting colon notation for argument {index}: "{name1}" and "{name2}".'
                    ).format(
                        index=index + low,
                        name1=fin[index].annotation.__name__,
                        name2=anno.__name__,
                    )
                )
            if anno is not Parameter.empty:
                fin[index] = fin[index].replace(annotation=anno)
        # consume rest
        fin[-1] = fin[-1].replace(kind=Parameter.KEYWORD_ONLY)
        # name the parameters for the help text
        for i, param in enumerate(fin):
            anno = param.annotation
            name = "{}_{}".format(
                "text" if anno is Parameter.empty else anno.__name__.lower(),
                i if i < high else "final",
            )
            fin[i] = fin[i].replace(name=name)
        return dict((p.name, p) for p in fin)

    def test_cooldowns(self, ctx, command, cooldowns):
        now = datetime.utcnow()
        new_cooldowns = {}
        for per, rate in cooldowns.items():
            if per == "guild":
                key = (command, ctx.guild)
            elif per == "channel":
                key = (command, ctx.guild, ctx.channel)
            elif per == "member":
                key = (command, ctx.guild, ctx.author)
            else:
                raise ValueError(per)
            cooldown = self.cooldowns.get(key)
            if cooldown:
                cooldown += timedelta(seconds=rate)
                if cooldown > now:
                    raise OnCooldown()
            new_cooldowns[key] = now
        # only update cooldowns if the command isn't on cooldown
        self.cooldowns.update(new_cooldowns)

    @classmethod
    def transform_arg(cls, result, attr, obj) -> str:
        attr = attr[1:]  # strip initial dot
        if not attr:
            return cls.maybe_humanize_list(obj)
        raw_result = "{" + result + "}"
        # forbid private members and nested attr lookups
        if attr.startswith("_") or "." in attr:
            return raw_result
        return cls.maybe_humanize_list(getattr(obj, attr, raw_result))

    @staticmethod
    def maybe_humanize_list(thing) -> str:
        if isinstance(thing, str):
            return thing
        try:
            return humanize_list(list(map(str, thing)))
        except TypeError:
            return str(thing)

    @staticmethod
    def transform_parameter(result, message) -> str:
        """
        For security reasons only specific objects are allowed
        Internals are ignored
        """
        raw_result = "{" + result + "}"
        objects = {
            "message": message,
            "author": message.author,
            "channel": message.channel,
            "guild": message.guild,
            "server": message.guild,
        }
        if result in objects:
            return str(objects[result])
        try:
            first, second = result.split(".")
        except ValueError:
            return raw_result
        if first in objects and not second.startswith("_"):
            first = objects[first]
        else:
            return raw_result
        return str(getattr(first, second, raw_result))

    async def get_command_names(self, guild: discord.Guild) -> Set[str]:
        """Get all custom command names in a guild.

        Returns
        --------
        Set[str]
            A set of all custom command names.

        """
        return set(await CommandObj.get_commands(self.config.guild(guild)))

    @staticmethod
    def prepare_command_list(
        ctx: commands.Context, command_list: Iterable[Tuple[str, dict]]
    ) -> List[Tuple[str, str]]:
        results = []
        for command, body in command_list:
            responses = body["response"]
            if isinstance(responses, list):
                result = ", ".join(responses)
            elif isinstance(responses, str):
                result = responses
            else:
                continue
            # Cut preview to 52 characters max
            if len(result) > 52:
                result = result[:49] + "..."
            # Replace newlines with spaces
            result = result.replace("\n", " ")
            # Escape markdown and mass mentions
            result = escape(result, formatting=True, mass_mentions=True)
            results.append((f"{ctx.clean_prefix}{command}", result))
        return results

#######################################################################