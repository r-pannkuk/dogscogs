from datetime import datetime
from typing import Literal

import discord
import pytz
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

DISCORD_MAX_EMBED_DESCRIPTION_CHARCTER_LIMIT = 2048
DISCORD_MAX_MESSAGE_SIZE_LIMIT = 2000

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_MEMBER = {
    "is_locked": False,
    "locked_nick": None,
    "previous_nick": None,
    "last_updated": None,
    "last_locked": None
}

DEFAULT_GUILD = {
    "nicknamed_member_ids": []
}

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

    @commands.group(aliases=["nick", "name"])
    async def nickname(self, ctx: commands.Context):
        """Locks nickname changes for a user (setting them to a set nickname until unset).

        Args:
            ctx (commands.Context): Command Context.
        """
        pass
    
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command(usage="<member> <name>")
    async def set(self, ctx: commands.Context, member: discord.Member, *, name: str):
        """Sets a stuck nickname for the user until unset.

        Args:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member whose nickname is changing.
            name (str): The name to set for the user.
        """
        guild = ctx.guild


        original_name : str = member.display_name
        
        member_config = self.config.member(member)
        is_locked = await member_config.is_locked()

        try:
            await member_config.is_locked.set(False)

            await member.edit(reason=f"{ctx.author} locked nickname to {name}.", nick=name)

            await ctx.send(f"Locked {original_name}'s nickname to {name}.")

            await member_config.locked_nick.set(name)
            await member_config.last_updated.set(datetime.now().timestamp())
            if not is_locked:
                await member_config.previous_nick.set(original_name)
                await member_config.last_locked.set(datetime.now().timestamp())
            await member_config.is_locked.set(True)

            nicknamed_member_ids : list = await self.config.guild(guild).nicknamed_member_ids()
            nicknamed_member_ids.append(member.id)
            nicknamed_member_ids = list(set(nicknamed_member_ids))

            await self.config.guild(guild).nicknamed_member_ids.set(nicknamed_member_ids)
        except:
            await ctx.send(f"ERROR: Bot does not have permission to edit {original_name}'s nickname.")
            await member_config.is_locked.set(is_locked)

        pass

    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command(usage="<member>")
    async def unset(self, ctx: commands.Context, *, member: discord.Member):
        """Removes a stuck nickname for a user until unset.

        Args:
            ctx (commands.Context): Command Context
            member (discord.Member): The target member whose nickname is changing.
        """
        guild = ctx.guild

        member_config = self.config.member(member)
        
        previous_nick : str = await member_config.previous_nick()
        
        member_config = self.config.member(member)
        is_locked = await member_config.is_locked()

        try:
            await member_config.is_locked.set(False)
            await member.edit(reason=f"Unlocking nickname and setting back to normal.", nick=previous_nick)

            await ctx.send(f"Returned {member.name}'s nickname to {previous_nick}.")

            await member_config.last_updated.set(datetime.now().timestamp())

            nicknamed_member_ids : list = await self.config.guild(guild).nicknamed_member_ids()
            nicknamed_member_ids.remove(member.id)
            nicknamed_member_ids = list(set(nicknamed_member_ids))

            await self.config.guild(guild).nicknamed_member_ids.set(nicknamed_member_ids)
        except:
            await ctx.send(f"ERROR: Bot does not have permission to edit {previous_nick}'s nickname.")
            await member_config.is_locked.set(is_locked)

        pass

    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    @nickname.command()
    async def list(self, ctx: commands.Context):
        """Displays the list of all users whose nicknames are set.

        Args:
            ctx (commands.Context): Command Context.
        """
        guild : discord.Guild = ctx.guild
        member_ids : list = await self.config.guild(guild).nicknamed_member_ids()

        if len(member_ids) == 0:
            await ctx.send("No members currently have locked nicknames.")
        else:
            title = f"Locked Nicknames"
            
            values = []

            member : discord.Member
            for member in [guild.get_member(id) for id in member_ids]:
                last_locked = datetime.fromtimestamp(
                    await self.config.member(member).last_locked(),
                    tz=pytz.timezone("US/Eastern")
                )
                values.append((member, last_locked))
            
            # Sort by time locked.
            values = sorted(values, key=lambda v: v[1])
            
            while len(values) > 0:
                description = ""
                while len(values) > 0:
                    record = values[0]
                    member : discord.Member = record[0]
                    last_locked : datetime = record[1]

                    string = f"{member.mention} ({member.name}): {datetime.strftime(last_locked, '%b %d, %Y  %H:%M:%S')}\n"

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
                    title = title,
                    description = description
                )

                title = ""

                await ctx.send(embed=embed)
        pass

    @ commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        """Checks for member nickname changes and locks them if so.

        Args:
            before (discord.Member): Affected member state before change.
            after (discord.Member): Affected member state after change.
        """

        # Check if nickname didn't update
        if before.nick == after.nick:
            return

        member_config = self.config.member(before)

        # Check if nickname isn't locked.
        if not await member_config.is_locked():
            return
        
        # Check if nickname was changed to the locked nickname.
        if after.nick == await member_config.locked_nick():
            return


        await after.guild.get_member(after.id).edit(reason=f"Preventing user from changing nickname.", nick=await member_config.locked_nick())

        pass

    @ commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Restores user locked nicknames if they rejoin the server.

        Args:
            member (discord.Member): Affected member.
        """

        member_config = self.config.member(member)

        # Check if nickname isn't locked.
        if not await member_config.is_locked():
            return
        
        # Check if nickname was changed to the locked nickname.
        if member.nick == await member_config.locked_nick():
            return

        await member.guild.get_member(member.id).edit(reason=f"Updating user's nickname to locked nickname.", nick=await member_config.locked_nick())
        pass

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Not used.

        Args:
            member (discord.Member): Affected member.
        """
        pass