from datetime import timedelta
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from dogscogs.constants import COG_IDENTIFIER

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": True,
    "channel_id": None,
    "ban_message": "You've posted in a spam trap channel. Any messages sent in the channel will result in an automatic ban. Please contact the moderators if you believe this to be an error.",
    "timeout_secs": 0,
    "whitelist": {
        "roles": [],
        "members": [],
    },
}

class SpamTrap(commands.Cog):
    """
    Autobans and removes messages from a designated channel to catch spamming bots or compromised accounts.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)


    @commands.guild_only()
    @commands.has_permissions(manage_roles=True)
    @commands.group()
    async def spamtrap(self, ctx: commands.GuildContext) -> None:
        """Base command for spam trap settings."""
        pass
    
    @commands.guild_only()
    @spamtrap.command(name="enabled", aliases=["status", "toggle"])
    async def enabled(self, ctx: commands.GuildContext, b: typing.Optional[bool]) -> None:
        """Toggle the spam trap on or off for the server."""
        if b is None:
            current = await self.config.guild(ctx.guild).is_enabled()
            await ctx.send(f"The spam trap is currently {'enabled' if current else 'disabled'}.")
            return

        await self.config.guild(ctx.guild).is_enabled.set(b)
        await ctx.send(f"The spam trap has been {'enabled' if b else 'disabled'}.")

    @commands.guild_only()
    @spamtrap.command()
    async def enable(self, ctx: commands.GuildContext) -> None:
        """Enable the spam trap for the server."""
        await self.config.guild(ctx.guild).is_enabled.set(True)
        await ctx.send("The spam trap has been enabled.")

    @commands.guild_only()
    @spamtrap.command()
    async def disable(self, ctx: commands.GuildContext) -> None:
        """Disable the spam trap for the server."""
        await self.config.guild(ctx.guild).is_enabled.set(False)
        await ctx.send("The spam trap has been disabled.")


    @commands.guild_only()
    @spamtrap.command()
    async def channel(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]) -> None:
        """Set the spam trap channel.

        If no channel is provided, it will use the current channel.
        """
        if channel is None:
            channel_id = await self.config.guild(ctx.guild).channel_id()

            if channel_id is None:
                await ctx.send("No spam trap channel is currently set.")
                return
            
            channel = ctx.guild.get_channel(channel_id)
            if channel is None:
                await ctx.send("The previously set spam trap channel could not be found. Please set a new one.")
                await self.config.guild(ctx.guild).channel_id.set(None)
                return
            
        await self.config.guild(ctx.guild).channel_id.set(channel.id)
        await ctx.send(f"The spam trap channel has been set to {channel.mention}.")


    @commands.guild_only()
    @spamtrap.command(aliases=["ban_message", "msg"])
    async def message(self, ctx: commands.GuildContext, *, message: typing.Optional[str]) -> None:
        """Set the ban message sent to users who post in the spam trap channel.

        If no message is provided, it will show the current message.
        """
        if message is None:
            current_message = await self.config.guild(ctx.guild).ban_message()
            await ctx.send(f"The current spam trap ban message is:\n> {current_message}")
            return

        await self.config.guild(ctx.guild).ban_message.set(message)
        await ctx.send(f"The spam trap ban message has been updated to:\n> {message}")


    @commands.guild_only()
    @spamtrap.command()
    async def timeout(self, ctx: commands.GuildContext, seconds: typing.Optional[int]) -> None:
        """Set the duration (in seconds) for which a user is timed out when they post in the spam trap channel.

        Set to 0 to disable timeouts.
        """
        if seconds is None:
            current = await self.config.guild(ctx.guild).timeout_secs()
            if current == 0:
                await ctx.send("Timeouts are currently disabled. Users posting in the spam trap channel will be banned indefinitely.")
            else:
                await ctx.send(f"Users posting in the spam trap channel are currently timed out for {current} seconds.")
            return
        
        if seconds < 0:
            await ctx.send("Timeout duration cannot be negative.")
            return
        
        if seconds > 2_419_200:  # 28 days in seconds
            await ctx.send("Timeout duration cannot exceed 28 days (2,419,200 seconds).")
            return

        await self.config.guild(ctx.guild).timeout_secs.set(seconds)
        if seconds == 0:
            await ctx.send("Timeouts have been disabled.  Users posting in the spam trap channel will be banned indefinitely.")
        else:
            await ctx.send(f"Users posting in the spam trap channel will now be timed out for {seconds} seconds.")


    @commands.guild_only()
    @spamtrap.group()
    async def whitelist(self, ctx: commands.GuildContext) -> None:
        """Whitelist roles or members from being autobanned by the spam trap.
        """

    @commands.guild_only()
    @whitelist.command(name="add", aliases=["append"])
    async def whitelist_add(self, ctx: commands.GuildContext, role_or_ids: commands.Greedy[typing.Union[discord.Role, discord.Member]]) -> None:
        """
        Add roles or members to the spam trap whitelist.

        You can provide multiple roles or member IDs separated by spaces.
        ️Examples:
            `[p]spamtrap whitelist add @TrustedRole @AnotherRole`
            `[p]spamtrap whitelist add 123456789012345678 987654321098765432`
        """
        guild_config = await self.config.guild(ctx.guild).whitelist()
        added : typing.List[int] = []
        mentions : typing.List[str] = []
        for item in role_or_ids:
            if isinstance(item, discord.Role):
                guild_config["roles"].append(item.id)
                added.append(item.id)

            elif isinstance(item, discord.Member):
                guild_config["members"].append(item.id)
                added.append(item.id)

            else:
                raise commands.BadArgument(f"Could not find role or member for input: {item}")

            mentions.append(item.mention)

        guild_config["members"] = list(set(guild_config["members"]))
        guild_config["roles"] = list(set(guild_config["roles"]))

        await self.config.guild(ctx.guild).whitelist.set(guild_config)

        if len(added) > 0:
            await ctx.send("Whitelisted the following:\n" + "\n".join([f"- {mention}" for mention in mentions]), allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.send("No valid roles or members were provided to whitelist.")


    @commands.guild_only()
    @whitelist.command(name="remove", aliases=["delete", "del", "rm"])
    async def whitelist_remove(self, ctx: commands.GuildContext, role_or_ids: commands.Greedy[typing.Union[discord.Role, discord.Member]]) -> None:
        """
        Remove roles or members from the spam trap whitelist.

        You can provide multiple roles or member IDs separated by spaces.
        ️Examples:
            `[p]spamtrap whitelist remove @TrustedRole @AnotherRole`
            `[p]spamtrap whitelist remove 123456789012345678 987654321098765432`
        """
        guild_config = await self.config.guild(ctx.guild).whitelist()
        removed : typing.List[int] = []
        mentions : typing.List[str] = []

        not_found_mentions: typing.List[str] = []

        for item in role_or_ids:
            if isinstance(item, discord.Role):
                if item.id in guild_config["roles"]:
                    guild_config["roles"].remove(item.id)
                    removed.append(item.id)
                else:
                    not_found_mentions.append(item.mention)

            elif isinstance(item, discord.Member):
                if item.id in guild_config["members"]:
                    guild_config["members"].remove(item.id)
                    removed.append(item.id)
                else:
                    not_found_mentions.append(item.mention)

            else:
                raise commands.BadArgument(f"Could not find role or member for input: {item}")

            mentions.append(item.mention)

        await self.config.guild(ctx.guild).whitelist.set(guild_config)

        if len(removed) > 0:
            await ctx.send("Removed from whitelist the following:\n" + "\n".join([f"- {mention}" for mention in mentions]), allowed_mentions=discord.AllowedMentions.none())
        else:
            await ctx.send("No valid roles or members were provided to remove from the whitelist.")

        if len(not_found_mentions) > 0:
            await ctx.send("The following roles or members were not found in the whitelist:\n" + "\n".join([f"- {mention}" for mention in not_found_mentions]), allowed_mentions=discord.AllowedMentions.none())

    @commands.guild_only()
    @whitelist.command(name="list", aliases=["show"])
    async def whitelist_list(self, ctx: commands.GuildContext) -> None:
        """List all roles and members whitelisted from the spam trap."""
        guild_config = await self.config.guild(ctx.guild).whitelist()
        role_mentions = []
        member_mentions = []

        for role_id in guild_config["roles"]:
            role = ctx.guild.get_role(role_id)
            if role:
                role_mentions.append(role.mention)
            else:
                role_mentions.append(f"`{role_id}` (not found)")

        for member_id in guild_config["members"]:
            member = ctx.guild.get_member(member_id)
            if member:
                member_mentions.append(member.mention)
            else:
                member_mentions.append(f"`{member_id}` (not found)")

        embed = discord.Embed(title="Spam Trap Whitelist", color=discord.Color.blue())

        if role_mentions:
            embed.add_field(name="Whitelisted Roles", value="\n".join(role_mentions), inline=False)
        else:
            embed.add_field(name="Whitelisted Roles", value="No roles whitelisted.", inline=False)

        if member_mentions:
            embed.add_field(name="Whitelisted Members", value="\n".join(member_mentions), inline=False)
        else:
            embed.add_field(name="Whitelisted Members", value="No members whitelisted.", inline=False)

        await ctx.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())



    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Listener for messages sent in the spam trap channel."""
        if message.author.bot:
            return

        guild_config = await self.config.guild(message.guild).all()
        if not guild_config["is_enabled"]:
            return

        channel_id = guild_config["channel_id"]
        if channel_id is None or message.channel.id != channel_id:
            return

        # Check whitelist
        if message.author.id in guild_config["whitelist"]["members"]:
            return

        for role in message.author.roles:
            if role.id in guild_config["whitelist"]["roles"]:
                return

        timeout_duration = guild_config["timeout_secs"]
        ban_message = guild_config["ban_message"]

        try:
            if timeout_duration > 0:
                timeout_until = discord.utils.utcnow() + timedelta(seconds=timeout_duration)
                await message.author.timeout(timeout_until, reason="Posted in spam trap channel.")
                ban_message += f"\n\nYou are timed out until <t:{int(timeout_until.timestamp())}:F>."
            else:
                await message.author.ban(reason="Posted in spam trap channel.")

            try:
                await message.author.send(ban_message)
            except discord.Forbidden:
                pass  # Can't send DM to user

            await message.delete()
        except discord.Forbidden:
            # Log the lack of permissions or notify admins as needed
            print(f"Insufficient permissions to ban or timeout user {message.author} in guild {message.guild}.")
        except Exception as e:
            # Log the exception or handle it as needed
            print(f"Error handling spam trap message: {e}")
