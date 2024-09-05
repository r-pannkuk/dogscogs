from asyncio import sleep
import asyncio
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

FreezerEntryType = typing.Union[discord.CategoryChannel,
                                discord.VoiceChannel, discord.TextChannel]

INDENT_SIZE = 2

def run_once(f):
    def wrapper(*args, **kwargs):
        if not wrapper.has_run:
            wrapper.has_run = True
            return f(*args, **kwargs)
    wrapper.has_run = False
    return wrapper

def FreezerEntry(category_or_channel: FreezerEntryType):
    self = {}
    self["children"] = []
    self["id"] = category_or_channel.id
    self["name"] = category_or_channel.name
    self["category_id"] = category_or_channel.category_id
    if isinstance(category_or_channel, discord.CategoryChannel):
        self["type"] = 'CATEGORY'
        self["children"] = [
            FreezerEntry(channel) for channel in sorted(category_or_channel.channels, key=lambda c: c.position)
        ]
    elif isinstance(category_or_channel, discord.VoiceChannel):
        self["type"] = 'VOICE'
    elif isinstance(category_or_channel, discord.TextChannel):
        self["type"] = 'TEXT'
    self["position"] = category_or_channel.position

    return self


DEFAULT_GUILD = {
    "is_enabled": True,
    "freezer_entries": {},
    "is_moving_categories": False
}


class Freezer(commands.Cog):
    """
    Freezes channel ordering to ensure it stays consistent.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

        self.is_running = False

        self.current_movers : typing.List[FreezerEntry] = []
        pass

    async def sort_channels(self, guild: discord.Guild):
        freezer_entries: typing.Dict[int, FreezerEntry] = await self.config.guild(guild).freezer_entries()
        operations = []
        categories = guild.categories

        # Identify all of the channels that need to be corrected.
        for category in categories:
            if str(category.id) in freezer_entries.keys():
                correct_channels = sorted(freezer_entries[str(category.id)]['children'], key=lambda c: c['position'])
                
                for k in range(0, len(correct_channels)):
                    channel = next(c for c in category.channels if c.id == correct_channels[k]['id'])

                    # check for permissions
                    if channel.permissions_for(guild.me).manage_channels:
                        print(f"Channel {channel.name} is at position {channel.position} and should be at {correct_channels[k]['position']}")
                        operations.append(channel.edit(position=correct_channels[k]['position']))
                    

        if len(operations) > 0:
            await self.config.guild(guild).is_moving_categories.set(True)
            print("Running operations")
            for operation in operations:
                await operation
                await sleep(3)
            print("Done running operations")
            await self.config.guild(guild).is_moving_categories.set(False)


    @commands.group()
    @commands.mod_or_permissions(manage_channels=True)
    async def freezer(self, ctx: commands.Context):
        """Settings for freezing channel order and structure of server.
        """
        pass

    @freezer.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def enable(self, ctx: commands.Context):
        """Enable the freezer.
        """
        await self.config.guild(ctx.guild).is_enabled.set(True)
        await ctx.send("Freezer enabled.")
        pass

    @freezer.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def disable(self, ctx: commands.Context):
        """Disable the freezer.
        """
        await self.config.guild(ctx.guild).is_enabled.set(False)
        await ctx.send("Freezer disabled.")
        pass

    @freezer.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Check if the freezer is enabled.

        Args:
            bool (typing.Optional[bool]): Whether or not the freezer is enabled.
        """
        if bool is None:
            bool = await self.config.guild(ctx.guild).is_enabled()

        await self.config.guild(ctx.guild).is_enabled.set(bool)

        await ctx.send(f"Freezer is {'enabled' if bool else 'disabled'}.")
        pass

    @freezer.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def ismoving(self, ctx:commands.Context, bool: typing.Optional[bool]):
        """Check if the freezer is moving categories when a channel is moved.
        """
        if bool is None:
            bool = await self.config.guild(ctx.guild).is_moving_categories()

        await self.config.guild(ctx.guild).is_moving_categories.set(bool)

        await ctx.send(f"Currently {'moving' if bool else 'not moving'} channels.")
        pass

    @freezer.command(aliases=["lock"])
    @commands.mod_or_permissions(manage_channels=True)
    async def freeze(self, ctx: commands.Context, *, category: typing.Optional[typing.Union[str, discord.CategoryChannel]]):
        """Freezes a specific category channel, or all channels in the server.

        Args:
            category (typing.Optional[FreezerEntryType]): A category channel to limit reordering in.
        """
        freezer_entries: typing.Dict[int, FreezerEntry] = await self.config.guild(ctx.guild).freezer_entries()
        guild: discord.Guild = ctx.guild

        def freeze_entry(entry: FreezerEntryType):
            freezer_entries[entry.id] = FreezerEntry(entry)

        if isinstance(category, str):
            category = next(c for c in guild.categories if str.lower(
                c.name) == str.lower(category))

        if category:
            freeze_entry(category)
        else:
            for _category in guild.categories:
                freeze_entry(_category)
            for _channel in [c for c in guild.channels if c.category == None]:
                freeze_entry(_channel)
            pass

        await ctx.send(f"Froze {category.name if category != None else 'all channels'} successfully")

        await self.config.guild(ctx.guild).freezer_entries.set(freezer_entries)
        pass

    @freezer.command(aliases=["unlock"])
    @commands.mod_or_permissions(manage_channels=True)
    async def unfreeze(self, ctx: commands.Context, *, category: typing.Optional[typing.Union[str, discord.CategoryChannel]]):
        """Unlocks a specific cateogry channel, or all channels in the server.

        Args:
            category (typing.Optional[discord.CategoryChannel]): A category channel to unlock reordering on.
        """
        freezer_entries: typing.Dict[int, FreezerEntry] = await self.config.guild(ctx.guild).freezer_entries()
        guild: discord.Guild = ctx.guild

        def unfreeze_entry(entry: FreezerEntryType):
            if str(entry.id) in freezer_entries:
                freezer_entries.pop(str(entry.id))
            pass

        if isinstance(category, str):
            category = next(c for c in guild.categories if str.lower(
                c.name) == str.lower(category))

        if category:
            unfreeze_entry(category)
        else:
            for _category in guild.categories:
                unfreeze_entry(_category)
            pass

        await ctx.send(f"Unfroze {category.name if category != None else 'all channels'} successfully")

        await self.config.guild(ctx.guild).freezer_entries.set(freezer_entries)
        pass

    @freezer.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def state(self, ctx: commands.Context):
        """Displays the current state of any active locks on the server's channels.
        """
        freezer_entries: typing.Dict[int, FreezerEntry] = await self.config.guild(ctx.guild).freezer_entries()
        guild: discord.Guild = ctx.guild

        embed = discord.Embed()
        embed.title = "Frozen channel order of the following:"

        description = []

        def stringify_entry(entry: FreezerEntry, indent_length=0):
            found_channel: FreezerEntryType = next(
                (channel for channel in guild.channels if channel.id == entry['id'])
            , None)
            if found_channel:
                if isinstance(found_channel, discord.VoiceChannel):
                    icon = '🔊'
                elif isinstance(found_channel, discord.TextChannel):
                    icon = '#️⃣'
                else: 
                    icon = '🔻'
                description.append(
                    f"{' '.join([' '] * indent_length)}{icon}{found_channel.name}   --   {found_channel.position} (recorded: {entry['position']})"
                )
                if entry['type'] == 'CATEGORY':
                    for child in entry['children']:
                        stringify_entry(child, indent_length + INDENT_SIZE)
            else:
                if entry['id'] in freezer_entries:
                    freezer_entries.pop(entry['id'])
            pass

        if len(dict.keys(freezer_entries)) != 0:
            for entry in sorted(freezer_entries.values(), key=lambda x: x["position"]):
                    stringify_entry(entry)
            embed.description = '`' + ('\n').join(description) + '`'
        else:
            embed.description = f"`*No Channels Currently Frozen*`"

        await ctx.send(embed=embed)
        await self.config.guild(ctx.guild).freezer_entries.set(freezer_entries)

        pass

    @freezer.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def sort(self, ctx: commands.GuildContext):
        """Sorts the channel order to the recorded state.
        """
        await self.sort_channels(ctx.guild)
        pass

    @freezer.group()
    @commands.mod_or_permissions(manage_channels=True)
    async def settings(self, ctx: commands.Context):
        """Settings for freezing channel order and structure of server.
        """
        pass

    @settings.command()
    @commands.mod_or_permissions(manage_channels=True)
    async def categories(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Sets whether or not to move categories when a channel is moved.

        Args:
            bool (typing.Optional[bool]): Whether or not to move categories when a channel is moved.
        """
        if bool != None:
            await self.config.guild(ctx.guild).is_moving_categories.set(bool)
        
        bool = await self.config.guild(ctx.guild).is_moving_categories()

        await ctx.send(f"{'Will' if bool else 'Will not'} move categories when a channel is moved.")

        pass

    @commands.Cog.listener()
    async def on_guild_channel_update(self, before: FreezerEntryType, after: FreezerEntryType):
        """Listens for channel movement and resets as necessary.

        Args:
            before (FreezerEntryType): Before state of the channel.
            after (FreezerEntryType): After state of the channel.
        """
        if not await self.config.guild(before.guild).is_enabled():
            return
        
        if await self.config.guild(before.guild).is_moving_categories():
            return
        
        await self.sort_channels(before.guild)

        pass
