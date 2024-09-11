from itertools import permutations
from typing import Literal
import datetime

import asyncio
import typing
import discord
import contextlib
from discord import member
from discord.utils import get
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from json import JSONEncoder

import random

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.constants.discord.embed import (
    MAX_DESCRIPTION_LENGTH as EMBED_MAX_DESCRIPTION_LENGTH,
)
from dogscogs.constants.discord.channel import TEXT_TYPES as TEXT_CHANNEL_TYPES
from dogscogs.parsers.date import to_birthdate

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]


class BirthdayRecord:
    """A record for Birthdays that keeps track of firings."""

    def __init__(self, *args, **kwargs) -> None:
        """Initializes a Birthday Record object for storing birthdays.

        __Args__:
            active (bool): The state of the birthday record.
            member_id (int): The ID of the member this birthday record is for.
            birthday (datetime.datetime): The birthday to store.
            created (datetime.datetime): The creation date of this record.
            last_updated (datetime.datetime): The last time this record was updated.
            last_fired (datetime.datetime): The last time this Birthday Record was fired.
            num_fired (int): How many times this record has been fired.
        """
        self._active = kwargs.get("_active", True)
        self._member_id = kwargs.get("_member_id", None)
        self._birthday = kwargs.get("_birthday", datetime.datetime.utcnow().timestamp())
        self._created = kwargs.get("_created", datetime.datetime.utcnow().timestamp())
        self._last_updated = kwargs.get(
            "_last_updated", datetime.datetime.utcnow().timestamp()
        )
        self._last_fired = kwargs.get(
            "_last_fired", datetime.datetime.utcnow().timestamp()
        )
        self._num_firings = kwargs.get("_num_firings", 0)

        self._birthday = (
            datetime.datetime.fromtimestamp(self._birthday)
            .replace(year=1980, hour=0, minute=0, second=0, microsecond=0)
            .timestamp()
        )
        pass

    @property
    def active(self) -> bool:
        """The state of the birthday record.

        Returns:
            bool: Whether or not the birthday record is active.
        """
        return self._active

    @active.setter
    def active(self, bool: bool):
        self._active = bool

    @property
    def member_id(self) -> int:
        """The ID of the member this birthday record is for.

        Returns:
            int: The integer value member id.
        """
        return self._member_id

    @member_id.setter
    def member_id(self, id: int):
        self._member_id = id

    @property
    def birthday(self) -> datetime.datetime:
        """The birthday of the record.

        Returns:
            datetime.datetime: What date is registered as the birthday.
        """
        return datetime.datetime.fromtimestamp(self._birthday)

    @birthday.setter
    def birthday(self, date: datetime.datetime):
        self._birthday = date.timestamp()

    @property
    def created(self) -> datetime.datetime:
        """The creation date of this record.

        Returns:
            datetime.datetime: Date object for this creation.
        """
        return datetime.datetime.fromtimestamp(self._created)

    @created.setter
    def created(self, date: datetime.datetime):
        self._created = date.timestamp()

    @property
    def last_updated(self) -> datetime.datetime:
        """The last time this record was updated with new info.

        Returns:
            datetime.datetime: Date object for the last time this record was updated.
        """
        return datetime.datetime.fromtimestamp(self._last_updated)

    @last_updated.setter
    def last_updated(self, date: datetime.datetime):
        self._last_updated = date.timestamp()

    @property
    def last_fired(self) -> datetime.datetime:
        """The last time this Birthday Record was fired.

        Returns:
            datetime.datetime: The date of the previous firing.
        """
        return datetime.datetime.fromtimestamp(self._last_fired)

    @last_fired.setter
    def last_fired(self, date: datetime.datetime):
        self._last_fired = date.timestamp()

    @property
    def num_firings(self) -> int:
        """How many times this record has been fired.

        Returns:
            int: The number of instances this record fired.
        """
        return self._num_firings

    @num_firings.setter
    def num_firings(self, num: int):
        self._num_firings = num

    @property
    def month(self) -> str:
        """Returns the month of the birthday.

        Returns:
            str: The string month of the birthday date object.
        """
        return self.birthday.strftime("%b")

    @property
    def day(self) -> str:
        """Returns the day of the birthday.

        Returns:
            str: The string day of the birthday date object.
        """
        return self.birthday.strftime("%d")

    @property
    def to_string(self) -> str:
        """Returns the full string of the birthday.

        Returns:
            str: The string of the birthday date object.
        """
        return f"{self.month} {self.day}"


class BirthdayRecordEncoder(JSONEncoder):
    def default(self, o):
        if isinstance(o, BirthdayRecord):
            return o.__dict__
        return JSONEncoder.default(self, o)

    pass


DEFAULT_GUILD = {
    "birthday_records_list": [],
    "current_birthday_member_ids": [],
    "default_role_name": None,
    "channel_id": None,
    "role_id": None,
}  # type: ignore[var-annotated]


class Birthday(commands.Cog):
    """Manages birthday notifications."""

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config: Config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        # self.config.register_member(**DEFAULT_MEMBER)

        self.config.register_guild(**DEFAULT_GUILD)

        # self.config.register_role(**DEFAULT_ROLE)

        # self.config.register_channel(**DEFAULT_CHANNEL)

        asyncio.ensure_future(self.post_initialize())
        return

    async def post_initialize(self):
        """Continuous polling for checking birthdays."""
        await self.bot.wait_until_ready()
        with contextlib.suppress(RuntimeError):
            # Stops the loop when the cog is reloaded
            while self == self.bot.get_cog(self.__class__.__name__):
                now = (
                    datetime.datetime.utcnow()
                    .replace(tzinfo=pytz.UTC)
                    .astimezone(tz=TIMEZONE)
                )
                tomorrow = (now + datetime.timedelta(days=1)).replace(
                    hour=9, minute=0, second=0, microsecond=0
                )

                await asyncio.sleep((tomorrow - now).total_seconds())

                await self.fire_today_birthdays()
        pass

    def birthday_message(self, member: discord.Member, date: datetime.datetime):
        """Obtains a proper birthday message for the given user and date.

        __Args__:
            member (typing.Union[discord.Member, str]): The user.
            date (datetime.datetime): The date for their birthday.
        """
        options = []

        if date.month == 1 and date.day == 1:
            options.append("Happy New Year, and Happy New Birthday {USER}.")
        if date.month == 7 and date.day == 4:
            options.append("Happy Birthday to AMERICA (and {USER}).")
        elif date.month == 9 and date.day == 9:
            options.append("Happy ⑨ Day, {USER}!")
        elif date.month == 10 and date.day == 31:
            options.append(
                "{USER} will gladly take all of your candy for their birthday."
            )
        elif date.month == 12 and date.day == 13:
            if member.id == 174037015858249730:
                options.append(
                    "Happy {USER} Day! Please donate to your local Hazelyn Foundation to remain in good standing."
                )
            else:
                options.append(
                    "Pretty sure this day is reserved for Birthdays, {USER}. Try choosing another one."
                )
        elif date.month == 12 and date.day == 25:
            options.append("Really? {USER} was born on Christmas?")
        elif date.day == 13 and date.weekday() == 4:
            options.append("A Friday the 13th birthday. Spooky, {USER}.")
        else:
            options.append("Everybody challenge {USER} to a FT5.  It's their birthday.")
            options.append("Happy {USER} Day, everyone!")
            options.append("Happy birthday {USER}!")
        return random.choice(options)

    async def fire_guild_birthday_list(self, guild: discord.Guild, predicate):
        role = guild.get_role(await self.config.guild(guild).role_id())
        raw = await self.config.guild(guild).birthday_records_list()
        records: typing.Dict[int, BirthdayRecord] = {
            BirthdayRecord(**r).member_id: BirthdayRecord(**r) for r in raw
        }
        now = datetime.datetime.now()

        birthday_member_ids = [
            member_id for member_id, record in records.items() if predicate(record)
        ]

        current_birthday_member_ids: typing.List[int] = await self.config.guild(
            guild
        ).current_birthday_member_ids()

        member: discord.Member

        # Remove old birthday emoji
        while len(current_birthday_member_ids) > 0:
            id = current_birthday_member_ids.pop()
            fetched_member = guild.get_member(id)
            if fetched_member is None:
                continue
            member = fetched_member

            try:
                await member.edit(nick=member.display_name.replace("🎉", ""))
            except:
                print(f"Couldn't edit member **{member.display_name}**.")
                pass

        for id in birthday_member_ids:
            records[id].last_fired = now
            records[id].num_firings += 1

            fetched_member = guild.get_member(id)
            if fetched_member is None:
                continue
            member = fetched_member

            channel = guild.get_channel(await self.config.guild(guild).channel_id())

            current_birthday_member_ids.append(member.id)

            try:
                await member.edit(nick=f"🎉{member.display_name}🎉")
            except:
                print(f"Couldn't edit member **{member.display_name}**.")
                pass

            if (
                channel is not None
                and role is not None
                and isinstance(channel, TEXT_CHANNEL_TYPES)
            ):
                await channel.send(
                    f"{role.mention} - {self.birthday_message(member, records[id].birthday.replace(year=now.year)).replace('{USER}', member.mention)}"
                )

        await self.config.guild(guild).current_birthday_member_ids.set(
            current_birthday_member_ids
        )
        pass

    async def fire_today_birthdays(self):
        """Performs the birthday execution at the given date / time."""
        guilds = self.bot.guilds
        now = datetime.datetime.now()

        for guild in guilds:
            await self.fire_guild_birthday_list(
                guild,
                lambda r: r.active == True
                and r.birthday.month == now.month
                and r.birthday.day == now.day,
            )
        pass

    async def set_birthday(
        self, member: discord.Member, date: datetime.datetime
    ) -> BirthdayRecord:
        """Sets a birthday record in the birthday record list and returns the entry.

        __Args__:
            member (discord.Member): The member to lookup a birthday for.
            date (datetime.datetime): The birthday to set.  Use format "MM/DD".

        Returns:
            BirthdayRecord: The entry in the Birthday records list.
        """
        guild = member.guild
        raw = await self.config.guild(guild).birthday_records_list()
        records: typing.Dict[int, BirthdayRecord] = {
            BirthdayRecord(**r).member_id: BirthdayRecord(**r) for r in raw
        }
        member_id: int = member.id

        if member_id in records:
            records[member_id].active = True
            records[member_id].birthday = date
            records[member_id].last_updated = datetime.datetime.now()
        else:
            records[member_id] = BirthdayRecord(
                _member_id=member_id, _birthday=date.timestamp()
            )

        raw = [record.__dict__ for key, record in records.items()]
        await self.config.guild(guild).birthday_records_list.set(raw)

        return records[member_id]

    async def unset_birthday(
        self, member: discord.Member
    ) -> typing.Union[BirthdayRecord, None]:
        """Deactivates a birthday record in the birthday record list and returns the entry.

        __Args__:
            member (discord.Member): The member to lookup a birthday for.

        Returns:
            BirthdayRecord: The entry in the Birthday records list.
        """
        guild = member.guild
        raw = await self.config.guild(guild).birthday_records_list()
        records: typing.Dict[int, BirthdayRecord] = {
            BirthdayRecord(**r).member_id: BirthdayRecord(**r) for r in raw
        }
        member_id: int = member.id

        if member_id in records:
            records[member_id].active = False
            records[member_id].last_updated = datetime.datetime.now()
        else:
            return None

        raw = [record.__dict__ for key, record in records.items()]
        await self.config.guild(guild).birthday_records_list.set(raw)

        return records[member_id]

    @commands.group()
    async def birthday(self, ctx: commands.GuildContext):
        """Commands for assigning and managing user birthdays.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        pass

    @birthday.command(usage="<date>")
    async def set(self, ctx: commands.GuildContext, *, date: to_birthdate):
        """Adds a user's birthday under the given date to the list.

        __Args__:
            ctx (commands.GuildContext): The command context.
            date (datetime.datetime): The date to set a birthday to.  Use format: `MM/DD`
        """
        record = await self.set_birthday(ctx.author, date)

        await ctx.send(
            f"**{ctx.author.display_name}** birthday registered to: `{record.month} {record.day}"
        )
        pass

    @birthday.command()
    async def unset(self, ctx: commands.GuildContext):
        """Removes a user's birrthday from the list.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        record = await self.unset_birthday(ctx.author)

        if record is None:
            await ctx.send(f"**{ctx.author.display_name}** birthday was not found.")
            return

        await ctx.send(f"**{ctx.author.display_name}** birthday has been unset.")
        pass

    @birthday.command()
    async def list(self, ctx: commands.GuildContext):
        """Returns the list of birthdays by date.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        guild: discord.Guild = ctx.guild
        raw = await self.config.guild(guild).birthday_records_list()
        records: typing.Dict[int, BirthdayRecord] = {
            BirthdayRecord(**r).member_id: BirthdayRecord(**r) for r in raw
        }
        values: typing.List[BirthdayRecord] = [
            value for key, value in records.items() if value.active == True
        ]

        if len(values) == 0:
            await ctx.send(f"No birthdays were found.")
            return

        def sorter(record: BirthdayRecord) -> typing.Tuple[datetime.datetime, str]:
            """Sorting function for birthday records (by next available date).

            __Args__:
                record (BirthdayRecord): Birthday record for comparison.

            Returns:
                datetime.datetime: Next occurrence of this birthday.
            """
            date = record.birthday
            now = datetime.datetime.utcnow()
            now = now.replace(year=1980)
            date = date.replace(year=1980)

            if date < now:
                date = date.replace(year=date.year + 1)

            fetched_member = guild.get_member(record.member_id) or self.bot.get_user(
                record.member_id
            )

            if fetched_member is None:
                return (date, str(record.member_id))

            return (date, fetched_member.display_name)

        values.sort(key=sorter)

        title = f"Upcoming Birthdays:"

        while len(values) > 0:
            description = ""

            while len(values) > 0:
                record = values[0]

                fetched_member = guild.get_member(record.member_id)
                if fetched_member is None:
                    continue
                member = fetched_member

                string = f"{record.to_string}: {member.mention}\n"

                if len(description) + len(string) > EMBED_MAX_DESCRIPTION_LENGTH:
                    break

                description += string

                values.pop(0)

            if len(description) == 0:
                await ctx.send(f"Something went wrong.")
                await self.bot.send_to_owners(
                    f"""`birthday: Failed to generate birthday list.
                -- guild: {guild.name} <{guild.id}>
                -- ignore_list: {values}`"""
                )
                return

            embed = discord.Embed(title=title, description=description)

            title = ""

            await ctx.send(embed=embed)
        pass

    @birthday.command()
    async def addme(self, ctx: commands.GuildContext):
        """Gives the user the role that will be pinged on birthdays.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        guild: discord.Guild = ctx.guild
        member: discord.Member = ctx.author
        role = guild.get_role(await self.config.guild(guild).role_id())

        if role is None:
            await ctx.send(
                f"Birthday role is not currently set up! Please ask the mods to create one."
            )
            return

        if role in member.roles:
            await ctx.send(
                f"**{member.display_name}** already has the **{role.name}** role."
            )
            return

        await member.add_roles(role)

        await ctx.send(
            f"**{member.display_name}** now has the role **{role.name}** and will be pinged on birthdays."
        )
        pass

    @birthday.command()
    async def removeme(self, ctx: commands.GuildContext):
        """Removes from the user the role that will be pinged on birthdays.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        guild: discord.Guild = ctx.guild
        member: discord.Member = ctx.author
        role = guild.get_role(await self.config.guild(guild).role_id())

        if role is None:
            await ctx.send(f"Birthday role is not currently set up!")
            return

        if role not in member.roles:
            await ctx.send(
                f"**{member.display_name}** does not have the **{role.name}** role."
            )
            return

        await member.remove_roles(role)

        await ctx.send(
            f"**{member.display_name}** no longer has the role **{role.name}** and will not be pinged on birthdays."
        )
        pass

    @birthday.group()
    @commands.has_guild_permissions(manage_roles=True)
    async def config(self, ctx: commands.GuildContext):
        """Config options for the birthday cog.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        pass

    @config.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """Sets or displays the channel for birthday messages.

        __Args__:
            ctx (commands.GuildContext): The command context.
            channel (typing.Optional[discord.TextChannel]): A channel to set the outputs to.
        """
        if channel is None:
            channel_id = await self.config.guild(ctx.guild).channel_id()
            fetched_channel = ctx.guild.get_channel(channel_id)

            if fetched_channel is None:
                self.config.guild(ctx.guild).channel_id.clear()
                await ctx.reply(f"Birthday message channel is not currently set.")
                return
            
            channel = fetched_channel # type: ignore[assignment]

        await self.config.guild_from_id(ctx.guild.id).channel_id.set(channel.id) # type: ignore[union-attr]
        await ctx.reply(f"Birthday messages will be sent to **{channel.name}**.") # type: ignore[union-attr]

    @config.command()
    @commands.has_guild_permissions(manage_roles=True)
    async def role(
        self, ctx: commands.GuildContext, role: typing.Optional[discord.Role]
    ):
        """Sets or displays the role for birthday messages.

        __Args__:
            ctx (commands.GuildContext): The command context.
            role (typing.Optional[discord.Role]): A role to assign pings to.
        """
        if role is None:
            role_id = await self.config.guild(ctx.guild).role_id()
            fetched_role = ctx.guild.get_role(role_id)

            if fetched_role is None:
                self.config.guild(ctx.guild).role_id.clear()
                await ctx.reply(f"Birthday role is not currently set.")
                return

            role = fetched_role

        await self.config.guild(ctx.guild).role_id.set(role.id)
        await ctx.reply(f"Birthday role is now set to **{role.name}**.")
        pass

    @birthday.group()
    @commands.has_guild_permissions(manage_roles=True)
    async def manual(self, ctx: commands.GuildContext):
        """Manually overrides birthdays for users.

        __Args__:
            ctx (commands.GuildContext): The command context.
        """
        pass

    @manual.command(aliases=["set"])
    @commands.has_guild_permissions(manage_roles=True)
    async def add(
        self, ctx: commands.GuildContext, member: discord.Member, date: to_birthdate
    ):
        """Sets a user's birthday in the birthday list.

        __Args__:
            ctx (commands.GuildContext): The command context.
            member (discord.Member): The member to override.
            date (date): The date to set the birthday to.
        """
        record = await self.set_birthday(member, date)

        await ctx.send(
            f"**{member.display_name}** birthday registered to: `{record.month} {record.day}"
        )
        pass

    @manual.command(aliases=["remove", "unset"])
    @commands.has_guild_permissions(manage_roles=True)
    async def purge(self, ctx: commands.GuildContext, member: discord.Member):
        """Removes a user's birthday in the birthday list.

        __Args__:
            ctx (commands.GuildContext): The command context.
            member (discord.Member): The member to purge from the birthday list.
        """
        record = await self.unset_birthday(member)

        if record is None:
            await ctx.send(f"**{member.display_name}** birthday was not found.")
            return

        await ctx.send(f"**{member.display_name}** birthday has been unset.")
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Deactivates a birthday when a user leaves the server.

        __Args__:
            member (discord.Member): The leaving member.
        """
        guild = member.guild
        raw = await self.config.guild(guild).birthday_records_list()
        records: typing.Dict[int, BirthdayRecord] = {
            BirthdayRecord(**r).member_id: BirthdayRecord(**r) for r in raw
        }
        member_id: int = member.id

        if member_id in records:
            if records[member_id].active:
                records[member_id].active = False
                records[member_id].last_updated = datetime.datetime.utcnow()
            else:
                records.pop(member_id)

        raw = [record.__dict__ for key, record in records.items()]
        await self.config.guild(guild).birthday_records_list.set(raw)
        pass

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Activates a user's birthday when they join the server.

        __Args__:
            member (discord.Member): The joining member.
        """
        guild = member.guild
        raw = await self.config.guild(guild).birthday_records_list()
        records: typing.Dict[int, BirthdayRecord] = {
            BirthdayRecord(**r).member_id: BirthdayRecord(**r) for r in raw
        }
        member_id: int = member.id

        if member_id in records:
            if not records[member_id].active:
                records[member_id].active = True
                records[member_id].last_updated = datetime.datetime.utcnow()

        raw = [record.__dict__ for key, record in records.items()]
        await self.config.guild(guild).birthday_records_list.set(raw)
        pass

    @commands.is_owner()
    @birthday.command()
    async def test(self, ctx: commands.GuildContext):
        """WARNING: This fires EVERY birthday in the designated channel. Use at risk or be an annoying jerk again.

        Args:
            ctx (commands.GuildContext): _description_
        """
        guild: discord.Guild = ctx.guild
        await self.fire_guild_birthday_list(guild, lambda r: r.active)
        pass

    @commands.is_owner()
    @birthday.command(hidden=True)
    async def delete_all(self, ctx: commands.GuildContext):
        await self.config.guild(ctx.guild).clear()
