import asyncio
from datetime import datetime
from enum import Enum
from types import MethodType
from typing import Dict, Literal
import typing
from apscheduler.job import Job
import d20
import uuid

import discord
from discord.errors import Forbidden, InvalidArgument
import pytz
from redbot.core import commands
from redbot.core import config
from redbot.core.bot import Red
from redbot.core.config import Config

from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler(timezone="US/Eastern")

DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT = 2048
DISCORD_MAX_MESSAGE_SIZE_LIMIT = 2000

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


def NickQueueEntry(
    name: str,
    target_id: int,
    author_id: int,
    type="Default",
    created_at: datetime = 0,
    expiration: datetime = None
):
    retval = {}
    retval["name"] = name
    retval["target_id"] = target_id
    retval["author_id"] = author_id
    retval["type"] = type
    retval["created_at"] = created_at
    retval["expiration"] = expiration
    retval["id"] = uuid.uuid4().int
    return retval


DEFAULT_MEMBER = {
    "nick_queue": [],
    "next_curse_available": None
}

DEFAULT_GUILD = {
    "nicknamed_member_ids": [],
    "attacker_wins_ties": True,
    "attacker_strength": "1d20",
    "defender_strength": "1d20",
    "curse_cooldown": 12 * 60 * 60,  # 12 hours
    "curse_duration": 30 * 60 # 30 minutes
}


def bind_member(group: config.Group):

    async def is_type(self, type):
        nick_queue: typing.List[NickQueueEntry] = await self.nick_queue()
        return any(entry["type"] == type for entry in nick_queue)

    async def is_locked(self):
        return await is_type(self, "Locked")

    async def is_cursed(self):
        return await is_type(self, "Cursed")
    group.is_type = MethodType(is_type, group)
    group.is_locked = MethodType(is_locked, group)
    group.is_cursed = MethodType(is_cursed, group)

    async def get_author_id(self, type):
        nick_queue: typing.List[NickQueueEntry] = await self.nick_queue()
        entry: typing.List[NickQueueEntry] = list(filter(
            lambda entry: entry["type"] == type, nick_queue))
        if len(entry) == 0:
            return None
        else:
            return entry[0]["author_id"]

    async def get_locking_author_id(self):
        return await get_author_id(self, "Locked")

    async def get_cursing_author_id(self):
        return await get_author_id(self, "Cursed")
    group.get_author_id = MethodType(get_author_id, group)
    group.get_locking_author_id = MethodType(get_locking_author_id, group)
    group.get_cursing_author_id = MethodType(get_cursing_author_id, group)

    async def get_latest(self, type: typing.Optional[str] = None):
        nick_queue: typing.List[NickQueueEntry] = await self.nick_queue()
        if len(nick_queue) == 0:
            return None
        if type is not None:
            nick_queue = list(filter(
                lambda entry: entry["type"] == type, nick_queue))
        if len(nick_queue) == 0:
            return []

        return max(nick_queue, key=lambda entry: entry["created_at"])

    async def get_latest_curse(self):
        return await self.get_latest("Cursed")

    async def get_latest_lock(self):
        return await self.get_latest("Locked")

    async def get_original(self):
        return await self.get_latest("Default")
    group.get_latest = MethodType(get_latest, group)
    group.get_latest_curse = MethodType(get_latest_curse, group)
    group.get_latest_lock = MethodType(get_latest_lock, group)
    group.get_original = MethodType(get_original, group)

    async def remove_job(self, entry: NickQueueEntry = None, id: int = None):
        """Removes a job from the scheduler for the NickQueueEntry.

        Args:
            entry (NickQueueEntry, optional): The entry to query against. Defaults to None.
            id (int, optional): An ID for an entry to find. Defaults to None.

        Raises:
            InvalidArgument: If neither an entry nor id were presented, or if the ID was invalid.
        """
        if entry is None and id is None:
            raise InvalidArgument(
                "Need to have a valid entry or id to remove a job.")
        elif entry is None:
            nick_queue = await self.nick_queue()
            found = list(filter(lambda entry: (
                id in entry and entry["id"] == id), nick_queue))
            if len(found) == 0:
                raise InvalidArgument("ID was not found.")
            entry = found[0]
        if id not in entry:
            return

        job = scheduler.get_job(str(entry["id"]))
        if job is not None:
            scheduler.remove_job(str(entry["id"]))

    async def remove(self, type: str = None, id: int = None):
        original_queue: typing.List[NickQueueEntry] = await self.nick_queue()
        if len(original_queue) == 0:
            return
        found = list(
            filter(
                lambda entry:
                    entry["type"] == type or (
                        id in entry and entry["id"] == id
                    ),
                original_queue
            )
        )
        for entry in found:
            await self.remove_job(entry=entry)
        nick_queue = list(
            filter(lambda entry: entry not in found, original_queue)
        )
        await group.nick_queue.set(nick_queue)

    async def remove_lock(self):
        return await remove(self, type="Locked")

    async def remove_curse(self):
        return await remove(self, type="Cursed")

    async def remove_original(self):
        return await remove(self, type="Default")
    group.remove_job = MethodType(remove_job, group)
    group.remove = MethodType(remove, group)
    group.remove_lock = MethodType(remove_lock, group)
    group.remove_curse = MethodType(remove_curse, group)
    group.remove_original = MethodType(remove_original, group)

    async def add_entry(self, *, entry):
        nick_queue: typing.List[NickQueueEntry] = await self.nick_queue()
        nick_queue.append(entry)
        await self.nick_queue.set(nick_queue)
    group.add_entry = MethodType(add_entry, group)

    async def replace_original(self,
                               name: typing.Optional[str]):
        nick_queue: typing.List[NickQueueEntry] = await self.nick_queue()
        filtered = list(filter(
            lambda entry: entry["type"] == "Default", nick_queue))
        to_be_replaced = None
        if len(filtered) > 0:
            to_be_replaced = filtered[0]
        nick_queue = list(filter(
            lambda entry: entry["type"] != "Default", nick_queue))
        if to_be_replaced == None:
            to_be_replaced = NickQueueEntry(
                name="",
                target_id=to_be_replaced["target_id"],
                author_id=None,
                created_at=0
            )

        to_be_replaced["name"] = name

        nick_queue.append(to_be_replaced)
        await self.nick_queue.set(nick_queue)

    group.replace_original = MethodType(replace_original, group)
    return group


class Nickname(commands.Cog):
    """
    Prevents reassigning nicknames of users until command is disabled.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_member(**DEFAULT_MEMBER)

        self.config.register_guild(**DEFAULT_GUILD)

        scheduler.start()
        pass

    @commands.group(aliases=["nick", "name"])
    async def nickname(self, ctx: commands.Context):
        """Locks nickname changes for a user (setting them to a set nickname until unset).

        __Args__:
            ctx (commands.Context): Command Context.
        """
        pass

    @nickname.command(hidden=True)
    @commands.is_owner()
    async def clear(self, ctx: commands.Context, member: discord.Member):
        await self.config.member(member).clear()
        await ctx.send(f"Data cleared for {member.mention}.")

    async def _set(self,
                   member: discord.Member,
                   entry
                   ):
        guild = member.guild
        author = guild.get_member(entry["author_id"])

        member_config = bind_member(self.config.member(member))

        original = await member_config.get_original()

        if original is None:
            await member_config.add_entry(entry=NickQueueEntry(
                name=member.display_name,
                target_id=member.id,
                author_id=None,
                type="Default",
                created_at=0
            ))

        if entry["type"] == "Locked":
            await member_config.remove_lock()
        elif entry["type"] == "Cursed":
            await member_config.remove_curse()

        await member_config.add_entry(entry=entry)
        await member.edit(reason=f"{author.display_name} locked nickname to {entry['name']}.", nick=entry["name"])

        member_ids = await self.config.guild(guild).nicknamed_member_ids()
        member_ids.append(member.id)
        member_ids = list(set(member_ids))

        await self.config.guild(guild).nicknamed_member_ids.set(member_ids)

        return entry

    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command(aliases=["lock"], usage="<member> <name>")
    async def set(self, ctx: commands.Context, member: discord.Member, *, name: str):
        """Sets a stuck nickname for the user until unset.

        __Args__:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member whose nickname is changing.
            name (str): The name to set for the user.
        """
        original_name: str = member.display_name
        entry = NickQueueEntry(
            name=name,
            target_id=member.id,
            author_id=ctx.author.id,
            type="Locked",
            created_at=datetime.now(tz=pytz.timezone("US/Eastern")).timestamp()
        )
        try:
            await self._set(member, entry=entry)
            await ctx.send(f"Locked {original_name}'s nickname to {name}.")
        except (PermissionError, Forbidden) as e:
            await ctx.send(f"ERROR: Bot does not have permission to edit {member.display_name}'s nickname.")
        pass

    @commands.guild_only()
    @nickname.command(usage="<member> <name>")
    async def curse(self, ctx: commands.Context, target: discord.Member, *, name: str):
        """Attempts to curse a member with a given nickname.

        __Args__:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member to be afflicted.
            name (str): The name to set for the user.
        """
        next_curse_available = await self.config.member(ctx.author).next_curse_available()

        if next_curse_available != None and next_curse_available > datetime.now(tz=pytz.timezone("US/Eastern")).timestamp():
            formatted_time = datetime.strftime(datetime.fromtimestamp(
                next_curse_available,
                tz=pytz.timezone("US/Eastern")
            ), '%b %d, %Y  %H:%M:%S')
            await ctx.reply(
                f"You aren't yet available to curse again.  Next available curse is at ``{formatted_time}``.")
            return

        global_curse_cooldown = await self.config.guild(ctx.guild).curse_cooldown()
        next_available = datetime.now(tz=pytz.timezone(
            "US/Eastern")).timestamp() + global_curse_cooldown
        await self.config.member(ctx.author).next_curse_available.set(next_available)
        cooldown_msg = f"Your ability to curse is on cooldown for {global_curse_cooldown / (60 * 60)} hours."

        curse_duration = await self.config.guild(ctx.guild).curse_duration()

        attacker_strength = await self.config.guild(ctx.guild).attacker_strength()
        defender_strength = await self.config.guild(ctx.guild).defender_strength()

        attacker_roll = d20.roll(attacker_strength)
        defender_roll = d20.roll(defender_strength)

        result_msg = f"(Attacker: {attacker_roll.result}) vs. (Defender: {defender_roll.result})\n"

        prefix = ""

        if await self.config.guild(ctx.guild).attacker_wins_ties():
            def predicate(x, y): return x >= y
        else:
            def predicate(x, y): return x > y

        if attacker_roll.crit == d20.CritType.FAIL:
            target = ctx.author
            prefix += f":skull: Oh no, something went wrong... :skull:\n"
            pass
        elif attacker_roll.crit == d20.CritType.CRIT:
            curse_duration *= 2
            prefix += f":dart: Your curse feels extra potent! :dart:\n"
            pass
        # elif defender_roll.crit == d20.CritType.FAIL:
        #     pass
        # elif defender_roll.crit == d20.CritType.CRIT:
        #     pass
        elif predicate(attacker_roll.total, defender_roll.total) == False:
            await ctx.reply(
                f":x: {result_msg}You failed to curse {target.display_name}.  {cooldown_msg}")
            return

        expiration = datetime.now(tz=pytz.timezone(
            "US/Eastern")).timestamp() + curse_duration
        original_name: str = target.display_name

        entry = NickQueueEntry(
            name=name,
            target_id=target.id,
            author_id=ctx.author.id,
            type="Cursed",
            created_at=datetime.now(
                tz=pytz.timezone("US/Eastern")).timestamp(),
            expiration=expiration
        )

        try:
            await self._set(target, entry=entry)

            await ctx.send(
                f"{prefix}:white_check_mark: {result_msg}Cursed {original_name}'s nickname to {name} for {curse_duration / (60)} minutes.  {cooldown_msg}")

            async def curse_end():
                try:
                    await self._unset(target, "Cursed")
                    await ctx.send(f"{ctx.author.display_name}'s Curse on {target.display_name} has ended.")
                except (PermissionError, Forbidden) as e:
                    await ctx.reply(f"ERROR: Bot does not have permission to edit {target.display_name}'s nickname. Your curse cooldown was refunded.")

            scheduler.add_job(curse_end,
                              id=str(entry["id"]),
                              trigger='date',
                              next_run_time=datetime.fromtimestamp(
                                  expiration,
                                  tz=pytz.timezone("US/Eastern")
                              ),
                              replace_existing=True
                              )
        except (PermissionError, Forbidden) as e:
            await self.config.member(ctx.author).next_curse_available.set(datetime.now(tz=pytz.timezone("US/Eastern")).timestamp())
            await ctx.reply(f"ERROR: Bot does not have permission to edit {target.display_name}'s nickname. Your curse cooldown was refunded.")
            return
        pass

    async def _unset(self,
                     member: discord.Member,
                     id) -> NickQueueEntry:
        """Removes a stuck nickname for a user.

        __Args__:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member whose nickname is changing.
        """
        guild = member.guild

        member_config = bind_member(self.config.member(member))

        await member_config.remove(id)

        latest = await member_config.get_latest()

        await member.edit(reason=f"Removing current lock on nickname.", nick=latest["name"])

        if not await member_config.is_cursed() and not await member_config.is_locked():
            member_ids = await self.config.guild(guild).nicknamed_member_ids()
            member_ids = list(filter(lambda x: x != member.id, member_ids))
            await self.config.guild(guild).nicknamed_member_ids.set(member_ids)

        return latest

    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command(aliases=["unlock"], usage="<member>")
    async def unset(self, ctx: commands.Context, *, member: discord.Member):
        """Removes a locked nickname for a user.

        __Args__:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member whose nickname is changing.
        """
        member_config = bind_member(self.config.member(member))

        if not await member_config.is_locked():
            await ctx.send(f"{member.display_name} isn't locked.")
            return

        original_name = member.display_name
        try:
            latest = await self._unset(member, "Locked")
            msg = f"Removed the lock on {original_name}, returning their nickname to {member.display_name}"
            if latest != None:
                msg += f" ({latest['type']})"
            await ctx.send(f"{msg}.")
        except (PermissionError, Forbidden) as e:
            await ctx.reply(f"ERROR: Bot does not have permission to edit {member.display_name}'s nickname. Your curse cooldown was refunded.")
        pass

    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command(usage="<member>")
    async def uncurse(self, ctx: commands.Context, *, member: discord.Member):
        """Removes a cursed nickname for a user.

        __Args__:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member whose nickname is changing.
        """
        member_config = bind_member(self.config.member(member))
        author: discord.Member = ctx.author

        if not await member_config.is_cursed():
            await ctx.send(f"{member.display_name} isn't cursed.")
            return

        if author.id != await member_config.get_cursing_author_id() and not author.guild_permissions.manage_roles:
            await ctx.send(
                f"You do not have permission to remove {member.display_name}'s curse.")
            return

        original_name = member.display_name

        try:
            latest = await self._unset(member, "Cursed")
            msg = f"Removed the curse on {original_name}, returning their nickname to {member.display_name}"
            if latest != None:
                msg += f" ({latest['type']})"
            await ctx.send(f"{msg}.")
        except (PermissionError, Forbidden) as e:
            await ctx.reply(f"ERROR: Bot does not have permission to edit {member.display_name}'s nickname. Your curse cooldown was refunded.")
        pass

    async def check(self, ctx: commands.Context, member: typing.Optional[discord.Member] = None, type: typing.Optional[str] = None):
        """Checks the remaining duration on a curse or the time since a name has been locked for a user.

        Args:
            ctx (commands.Context): Command Context.
            member (typing.Optional[discord.Member], optional): The member to check against. Defaults to None.
            type (typing.Optional[str], optional): What type of check to perform.. Defaults to None.
        """
        member_config = bind_member(self.config.member(member))
        ailments = [
            await member_config.get_latest_curse(),
            await member_config.get_latest_lock()
        ]
        ailments = list(filter(lambda x: x != [] and x is not None, ailments))

        if len(ailments) == 0:
            return None
        else:
            msg = ""

            fields = {}

            for ailment in ailments:
                fields["target"] = member.display_name
                fields["type"] = ailment['type']
                fields["author"] = ctx.guild.get_member(
                    ailment['author_id']).display_name
                fields["participle"] = f"{'until' if ailment['type'] == 'Cursed' else 'since'} "
                fields["time"] = datetime.strftime(datetime.fromtimestamp(
                    ailment['expiration' if ailment['type'] == 'Cursed' else 'created_at'], tz=pytz.timezone('US/Eastern')), '%b %d, %Y  %H:%M:%S')
                return fields
            pass
        pass

    @commands.guild_only()
    @nickname.command(usage="<member>")
    async def checkcurse(self, ctx: commands.Context, member: typing.Optional[discord.Member]):
        """Checks the remaining curse duration for a user.

        __Args__:
            ctx (commands.Context): Command Context
            member (typing.Optional[discord.Member], optional): The member to check against. Defaults to None.

        """
        if member is None:
            member = ctx.author

        fields = await self.check(ctx, member, "Cursed")
        if fields == None:
            await ctx.reply(f"{'You are' if member == ctx.author else f'{member.display_name} is'} not currently Cursed to a nickname.")
            return
        await ctx.reply(f"{fields['target']} is {fields['type']} by {fields['author']} {fields['participle']} `{fields['time']}`.")

    @commands.guild_only()
    @nickname.command(usage="<member>")
    async def checklock(self, ctx: commands.Context, member: typing.Optional[discord.Member]):
        """Checks the remaining lock duration for a user.

        __Args__:
            ctx (commands.Context): Command Context
            member (typing.Optional[discord.Member], optional): The member to check against. Defaults to None.
        """
        if member is None:
            member = ctx.author

        fields = await self.check(ctx, member, "Locked")
        if fields == None:
            await ctx.reply(f"{'You are' if member == ctx.author else f'{member.display_name} is'} not currently Locked to a nickname.")
            return
        await ctx.reply(f"{fields['target']} is {fields['type']} by {fields['author']} {fields['participle']} `{fields['time']}`.")

    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command()
    async def list(self, ctx: commands.Context):
        """Displays the list of all users whose nicknames are set.

        __Args__:
            ctx (commands.Context): Command Context.
        """
        guild: discord.Guild = ctx.guild
        member_ids: list = await self.config.guild(guild).nicknamed_member_ids()

        if len(member_ids) == 0:
            await ctx.send("No members currently have locked nicknames.")
        else:
            title = f"Cursed or Locked Nicknames"

            values = []

            member: discord.Member
            for member in [guild.get_member(id) for id in member_ids]:
                member_config = bind_member(self.config.member(member))

                nick_queue = await member_config.nick_queue()
                nick_queue = list(filter(
                    lambda entry: entry["type"] != "Default" and (
                        entry["expiration"] == None or
                        entry["expiration"] > datetime.now(
                            tz=pytz.timezone("US/Eastern")).timestamp()
                    ),
                    nick_queue)
                )

                values.extend(nick_queue)

            # Sort by time locked.
            values = sorted(
                values, 
                key=lambda x: x["expiration"] if x["type"] == "Cursed" else x["created_at"],
                reverse=True
            )

            while len(values) > 0:
                description = ""
                while len(values) > 0:
                    value = values[0]
                    time_field = ""
                    member = guild.get_member(value["target_id"])
                    author = guild.get_member(value["author_id"])

                    if value["type"] == "Cursed":
                        time_field = datetime.fromtimestamp(
                            value["expiration"], tz=pytz.timezone("US/Eastern"))
                    elif value["type"] == "Locked":
                        time_field = datetime.fromtimestamp(
                            value["created_at"], tz=pytz.timezone("US/Eastern"))

                    string = f"{member.mention} ({member.name}) was {value['type']} to `{value['name']}` by {author.mention}: "
                    string += f" {'Releases on' if value['type'] == 'Cursed' else 'Since'} `{datetime.strftime(time_field, '%b %d, %Y  %H:%M:%S')}`"

                    if value["type"] == "Cursed":
                        string = f":skull:{string}"
                    elif value["type"] == "Locked":
                        string = f":lock:{string}"

                    string += "\n"

                    if len(description) + len(string) > DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT:
                        break

                    description += string

                    values.pop(0)

                if len(description) == 0:
                    await ctx.send(f"Something went wrong.")
                    await self.bot.send_to_owners(f"""`nickname: Failed to generate nickname list.
                    -- guild: {guild.name} <{guild.id}>
                    -- nickname_list: {values}`""")

                embed = discord.Embed(
                    title=title,
                    description=description
                )

                title = ""

                await ctx.send(embed=embed)
                pass
        pass

    async def _check_member(self, member: discord.Member):
        member_config = bind_member(self.config.member(member))
        guild: discord.Guild = member.guild

        nick_queue = await member_config.nick_queue()
        nick_queue = list(
            filter(lambda entry: entry["type"] == "Cursed", nick_queue)
        )

        async def undo_curse():
            await self._unset(member, "Cursed")
            await member.send(f"{guild.get_member(curse['author_id']).display_name}'s Curse on you has ended.")

        for curse in nick_queue:
            if curse["expiration"] < datetime.now(tz=pytz.timezone("US/Eastern")).timestamp():
                await undo_curse()
                continue
            else:
                scheduler.add_job(undo_curse,
                                  id=str(curse["id"]),
                                  trigger='date',
                                  next_run_time=datetime.fromtimestamp(
                                      curse["expiration"],
                                      tz=pytz.timezone("US/Eastern")
                                  ),
                                  replace_existing=True
                                  )
                pass

    async def _check_guild(self, guild: discord.Guild):
        member_ids: list = await self.config.guild(guild).nicknamed_member_ids()

        if len(member_ids) == 0:
            return
        else:
            member: discord.Member
            for member in [guild.get_member(id) for id in member_ids]:
                await self._check_member(member)

    @ commands.Cog.listener()
    async def on_ready(self):
        for guild in self.bot.guilds:
            await self._check_guild(guild)

    @ commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Checks for member nickname changes and locks them if so.

        __Args__:
            before (discord.Member): Affected member state before change.
            after (discord.Member): Affected member state after change.
        """

        # Check if nickname didn't update
        if before.nick == after.nick:
            return

        member_config = bind_member(self.config.member(before))

        # Check if nickname isn't locked.
        if not await member_config.is_locked() and not await member_config.is_cursed():
            await member_config.replace_original(after.display_name)
            return

        # Check if nickname was changed to the locked nickname.
        latest = await member_config.get_latest()
        if latest == None or after.nick == latest["name"]:
            return

        await after.guild.get_member(after.id).edit(reason=f"Preventing user from changing nickname.", nick=latest["name"])

        pass

    @ commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Restores user locked nicknames if they rejoin the server.

        __Args__:
            member (discord.Member): Affected member.
        """

        member_config = bind_member(self.config.member(member))

        # Check if nickname isn't locked.
        if not await member_config.is_locked() and not await member_config.is_cursed():
            member_config.replace_original(member.display_name)
            return

        # Check if nickname was changed to the locked nickname.
        latest = await member_config.get_latest()
        if latest == None or member.nick == latest["name"]:
            return

        await member.guild.get_member(member.id).edit(reason=f"Updating user's nickname to locked nickname.", nick=latest["name"])
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Not used.

        __Args__:
            member (discord.Member): Affected member.
        """
        pass
