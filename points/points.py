import random
from typing import Literal
import typing
import datetime
import pytz

import discord
from redbot.core import commands, bank
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": False,
    "daily_award": 100,
    "daily_award_channels": [],
    "offset": -50000,
    "passive_chance": 0.005,
    "passive_award_amount": 100,
    "passive_max_count_per_day": 5,
    "passive_channels": [],
    "passive_award_responses": [
        "That was a particularly good statement. Here, have $POINTS$."
        "I don't like you, but I can't deny this take. Have $POINTS$.",
        "You're not as bad as I thought. Have $POINTS$.",
        "Your opinions continue to confuse me. Have $POINTS$.",
        "For your loyalty to the server, have $POINTS$.",
        "I'm insulted by this take, but I'll give you $POINTS$ anyway.",
        "Hazelyn told me to give $POINTS$ to the worst poster today. Here you go.",
        "I feel bad that you're constantly getting beat up in the server. Have $POINTS$.",
        "I'm sorry for the way you're treated. Have $POINTS$.",
        "Every once in a while I feel generous. Have $POINTS$. I hope you're happy.",
        "I'm not sure why you're still here, but have $POINTS$.",
        "You're not the worst. Have $POINTS$.",
        "You need to improve your skills. Maybe $POINTS$ can serve as motivation.",
        "Maybe if I give you $POINTS$ you'll shut up for once.",
        "You're annoying me. Will $POINTS$ make it stop?",
        "On the list of best users in the server, you're name isn't on it. Here's $POINTS$ anyway.",
        "Your skills might be a joke, but it makes me laugh. Here's $POINTS$.",
    ]
}

DEFAULT_USER = {
    "last_claim_timestamp": 0,
    "last_passive_timestamp": 0,
    "last_passive_count": 0,
}

timezone = pytz.timezone("US/Eastern")

class PercentageOrFloat(commands.Converter):
    async def convert(self, ctx, argument: str) -> float:
        try:
            is_percentage = False
            if argument.endswith("%"):
                argument = argument[:-1]
                is_percentage = True

            value = float(argument)
            if is_percentage:
                value /= 100
        except ValueError:
            raise commands.BadArgument("Invalid percentage. Must be a float.")
        
        if value < 0 or value > 1:
            raise commands.BadArgument("Invalid percentage. Must be between 0 and 1.")
        
        return value


class BalanceAdjustmentButtons(discord.ui.View):

    class _Modal(discord.ui.Modal, title="Placeholder"):
        answer = discord.ui.TextInput(label="Answer", style=discord.TextStyle.short)

        def __init__(self, ctx: commands.Context, target: discord.Member):
            super().__init__(timeout=None)
            self.ctx = ctx
            self.target = target

        async def init(self, *, title: str, label: str):
            """Fetch values from the bank."""
            currency_name = await bank.get_currency_name(self.ctx.guild)  # type: ignore[arg-type]
            self.title = title.replace("$POINTS$", currency_name)
            self.answer.label = label.replace("$POINTS$", currency_name)
            self.answer.required = True

        async def interaction_check(self, interaction: discord.Interaction):
            if not self.answer.value:
                raise commands.BadArgument("You must provide a value.")
            try:
                test = int(self.answer.value)
            except ValueError:
                raise commands.BadArgument(
                    "The value you provided is invalid. Please enter a positive integer."
                )
            return True

        async def on_error(self, interaction, error):
            await interaction.response.send_message(
                f"An error occurred: {error}", ephemeral=True, delete_after=10
            )
            pass

    class AddModal(_Modal):
        async def init(self):
            await super().init(
                title=f"How many $POINTS$ to award?",
                label="Amount",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_balance = await Points._add_balance(self.target, int(self.answer.value))  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Awarded {self.answer.value} to {self.target.mention}. New Balance: `{new_balance}`",
                delete_after=15,
            )

    class TakeModal(_Modal):
        async def init(self):
            await super().init(
                title=f"How many $POINTS$ to remove?",
                label="Amount",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_balance = await Points._remove_balance(self.target, int(self.answer.value))  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Removed {self.target.mention}'s balance by {self.answer.value}. New Balance: `{new_balance}`",
                delete_after=15,
            )

    class SetModal(_Modal):
        async def init(self):
            await super().init(
                title=f"What value to set $POINTS$ balance to",
                label=f"Amount",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_balance = await Points._set_balance(self.target, int(self.answer.value))  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Set {self.target.mention}'s balance to {new_balance}.",
                delete_after=15,
            )

    def __init__(self, ctx: commands.Context, target: discord.Member):
        super().__init__(timeout=None)
        self.ctx = ctx
        self.target = target

    @discord.ui.button(label="Add", style=discord.ButtonStyle.green)
    async def award(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "You don't have permission to award points.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.AddModal(self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Set", style=discord.ButtonStyle.blurple)
    async def set(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "You don't have permission to set points.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.SetModal(self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Remove", style=discord.ButtonStyle.red)
    async def take(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.moderate_members:
            await interaction.response.send_message(
                "You don't have permission to remove points.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.TakeModal(self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)


class Points(commands.Cog):
    """
    Manages local guild points.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)
        self.config.register_user(**DEFAULT_USER)
        pass

    @staticmethod
    async def _add_balance(user: discord.Member, amount: int) -> int:
        """Add balance to a user's account.

        Args:
            user (discord.Member): The target of depositing.
            amount (int): The amount to deposit.
        """
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Points",
            identifier=260288776360820736,
            force_registration=True,
        )
        offset = await config.guild(user.guild).offset()
        current_balance = await Points._get_balance(user)
        max_balance = await bank.get_max_balance(user.guild)  # type: ignore[arg-type]
        if current_balance + amount - offset > max_balance:
            amount = max_balance - current_balance - offset
        return await bank.deposit_credits(user, amount) + offset  # type: ignore[arg-type]

    @staticmethod
    async def _remove_balance(user: discord.Member, amount: int) -> int:
        """Remove balance from a user's account.

        Args:
            user (discord.Member): The target of withdrawing.
            amount (int): The amount to withdraw.
        """
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Points",
            identifier=260288776360820736,
            force_registration=True,
        )
        offset = await config.guild(user.guild).offset()
        # current_balance = await Points._get_balance(user)
        # if current_balance - amount < 0:
        #     amount = current_balance
        return await bank.withdraw_credits(user, amount) + offset  # type: ignore[arg-type]

    @staticmethod
    async def _is_daily_award_claimed(user: discord.Member) -> bool:
        """Check if a user has claimed their daily award.

        Args:
            user (discord.Member): The user to check.

        Returns:
            bool: True if the user has claimed their daily award, False otherwise.
        """
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Points",
            identifier=260288776360820736,
            force_registration=True,
        )
        last_claim_timestamp = await config.user(user).last_claim_timestamp()
        last_claim_time = datetime.datetime.fromtimestamp(
            last_claim_timestamp, tz=timezone
        )
        return last_claim_time.date() == datetime.datetime.now(tz=timezone).date()

    @staticmethod
    async def _set_balance(user: discord.Member, amount: int) -> int:
        """Set a user's balance.

        Args:
            user (discord.Member): The target of setting.
            amount (int): The amount to set.
        """
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Points",
            identifier=260288776360820736,
            force_registration=True,
        )

        offset = await config.guild(user.guild).offset()
        amount = amount - offset
        max_balance = await bank.get_max_balance(user.guild)  # type: ignore[arg-type]
        if amount > max_balance:
            amount = max_balance
        # if amount < 0:
        #     amount = 0
        return await bank.set_balance(user, amount) + offset

    @staticmethod
    async def _get_balance(user: discord.Member) -> int:
        """Gets a user's true balance by using the offset.

        Args:
            user (discord.Member): The target of getting balance.

        Returns:
            int: The user's balance.
        """
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Points",
            identifier=260288776360820736,
            force_registration=True,
        )
        offset = await config.guild(user.guild).offset()
        return await bank.get_balance(user) + offset

    @commands.group()
    async def points(self, ctx: commands.Context):
        """Manage local guild points."""
        pass

    @points.group()
    @commands.mod_or_permissions(manage_roles=True)
    async def settings(self, ctx: commands.Context):
        """Manage local guild points settings."""
        pass

    @settings.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def enable(self, ctx: commands.Context):
        """Enable points in this guild."""
        await self.config.guild(ctx.guild).is_enabled.set(True)
        await ctx.send("Points `ENABLED`.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def disable(self, ctx: commands.Context):
        """Disable points in this guild."""
        await self.config.guild(ctx.guild).is_enabled.set(False)
        await ctx.send("Points `DISABLED`.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Check or set if points are enabled in this guild.

        Args:
            bool (typing.Optional[bool]): Set if points are enabled or not.
        """
        if bool is None:
            bool = await self.config.guild(ctx.guild).is_enabled()

        await self.config.guild(ctx.guild).is_enabled.set(bool)
        await ctx.send(f"Points are {'`ENABLED`' if bool else '`DISABLED`'}.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def max(self, ctx: commands.Context, max: typing.Optional[int]):
        """Set the max balance for a user.

        Args:
            max (typing.Optional[int]): The max balance for a user.
        """
        offset = await self.config.guild(ctx.guild).offset()

        if max is None:
            max = await bank.get_max_balance(ctx.guild) + offset  # type: ignore[arg-type]

        await bank.set_max_balance(max - offset, ctx.guild)  # type: ignore[arg-type]
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.send(f"The max balance for {currency_name} is set to `{max}`.")
        pass

    @settings.group()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def name(self, ctx: commands.Context):
        """Manage the naming settings."""
        pass

    @name.command(name="bank")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def name_bank(self, ctx: commands.Context, *, name: typing.Optional[str]):
        """Set the bank name.

        Args:
            name (typing.Optional[str]): The name of the bank.
        """
        if name is None:
            name = await bank.get_bank_name(ctx.guild)  # type: ignore[arg-type]

        await bank.set_bank_name(name, ctx.guild)  # type: ignore[arg-type]
        await ctx.send(f"Using `{name}` as the bank name.")
        pass

    @name.command(name="currency")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def name_currency(self, ctx: commands.Context, *, name: typing.Optional[str]):
        """Set the local currency name.

        Args:
            name (typing.Optional[str]): The name of the local currency.
        """
        if name is None:
            name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]

        await bank.set_currency_name(name, ctx.guild)  # type: ignore[arg-type]
        await ctx.send(f"Using `{name}` as the local currency.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def default(self, ctx: commands.Context, int: typing.Optional[int]):
        """Set the default balance for a user.

        Args:
            int (typing.Optional[int]): The default balance for a user.
        """
        offset = await self.config.guild(ctx.guild).offset()
        if int is None:
            int = await bank.get_default_balance(ctx.guild) + offset  # type: ignore[arg-type]

        await bank.set_default_balance(int - offset, ctx.guild)  # type: ignore[arg-type]
        await ctx.send(f"The starting balance for a user is set to `{int}`.")
        pass

    @settings.group()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def daily(self, ctx: commands.Context):
        """Manage daily award settings."""
        pass

    @daily.command(name="amount")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def daily_amount(self, ctx: commands.Context, int: typing.Optional[int]):
        """Set the daily award for a user.

        Args:
            int (typing.Optional[int]): The daily award for a user.
        """
        if int is None:
            int = await self.config.guild(ctx.guild).daily_award()

        await self.config.guild(ctx.guild).daily_award.set(int)
        await ctx.send(f"The daily award is set to `{int}`.")
        pass

    @daily.command(name="channels")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def daily_channels(
        self, ctx: commands.Context, *channels: discord.TextChannel
    ):
        """Set the channels where the daily award can be claimed.

        Args:
            channels (discord.TextChannel): The channels where the daily award can be claimed.
        """
        if not channels:
            channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
            channels = [ctx.guild.get_channel(channel_id) for channel_id in channel_ids]
            channels = [channel for channel in channels if channel is not None]  # type: ignore[arg-type]
        await self.config.guild(ctx.guild).daily_award_channels.set(
            [channel.id for channel in channels]
        )
        await ctx.send(
            f"Daily award can be claimed in {', '.join([channel.mention for channel in channels])}."
        )
        pass

    @settings.command()
    @commands.guild_only()
    @commands.is_owner()
    async def offset(self, ctx: commands.Context, int: typing.Optional[int]):
        """Set the offset for the balance.

        Args:
            int (typing.Optional[int]): The offset for the balance.
        """
        if int is None:
            int = await self.config.guild(ctx.guild).offset()

        await self.config.guild(ctx.guild).offset.set(int)
        await ctx.send(f"The offset for the balance is set to `{int}`.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.is_owner()
    async def reset(self, ctx: commands.Context):
        """Reset all settings to default."""
        await self.config.guild(ctx.guild).clear()
        await ctx.send("Settings reset to default.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.is_owner()
    async def wipe(self, ctx: commands.Context):
        """Wipe all user data."""
        await bank.wipe_bank(ctx.guild)
        await self.config.clear_all_users()
        await ctx.send("All user data wiped.")
        pass

    @settings.group()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def passive(self, ctx: commands.Context):
        """Manages passive point generation settings."""
        pass

    @passive.command(name="chance")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def passive_chance(
        self, ctx: commands.Context, chance: typing.Optional[PercentageOrFloat]
    ):
        """Set the chance of passive point generation.

        Args:
            chance (typing.Optional[float]): The chance of passive point generation.
        """
        if chance is None:
            chance = await self.config.guild(ctx.guild).passive_chance()

        if chance > 1:
            chance = 1
        elif chance < 0:
            chance = 0

        await self.config.guild(ctx.guild).passive_chance.set(chance)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.send(
            f"The chance of passive {currency_name} generation is set to `{chance:,.2%}`."
        )
        pass

    @passive.command(name="amount")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def passive_amount(self, ctx: commands.Context, amount: typing.Optional[int]):
        """Set the amount of passive points generated.

        Args:
            amount (typing.Optional[int]): The amount of passive points generated.
        """
        if amount is None:
            amount = await self.config.guild(ctx.guild).passive_award_amount()

        await self.config.guild(ctx.guild).passive_award_amount.set(amount)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.send(
            f"The amount of passive {currency_name} generated is set to `{amount}`."
        )
        pass

    @passive.command(name="max")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def passive_max(self, ctx: commands.Context, max: typing.Optional[int]):
        """Set the max number of times passive points can be obtained daily.

        Args:
            max (typing.Optional[int]): The max number of instances allowed.
        """
        if max is None:
            max = await self.config.guild(ctx.guild).passive_max_count_per_day()

        await self.config.guild(ctx.guild).passive_max_count_per_day.set(max)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.send(
            f"The max number of instances passive {currency_name} can be earned daily is: `{max}`."
        )
        pass

    @passive.command(name="channels")
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def passive_channels(
        self, ctx: commands.Context, *channels: discord.TextChannel
    ):
        """Set the channels where passive points can be obtained.

        Args:
            channels (discord.TextChannel): The channels where passive points can be obtained.
        """
        if not channels:
            channel_ids = await self.config.guild(ctx.guild).passive_channels()
            channels = [ctx.guild.get_channel(channel_id) for channel_id in channel_ids]
            channels = [channel for channel in channels if channel is not None]  # type: ignore[arg-type]
        await self.config.guild(ctx.guild).passive_channels.set(
            [channel.id for channel in channels]
        )
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]

        if len(channels) == 0:
            await ctx.send(f"Passive {currency_name} can be obtained in any channel.")
        else:
            await ctx.send(
                f"Passive {currency_name} can be obtained in {', '.join([channel.mention for channel in channels])}."
            )
        pass

    @points.command()
    @commands.guild_only()
    async def claim(self, ctx: commands.Context):
        """Claim your daily points."""
        tomorrow = (
            datetime.datetime.now(tz=timezone) + datetime.timedelta(days=1)
        ).replace(hour=0, minute=0, second=0, microsecond=0)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]

        if await Points._is_daily_award_claimed(ctx.author):
            await ctx.reply(
                f"You have already claimed your daily {currency_name}. Try again at <t:{int(tomorrow.timestamp())}:F>.",
                delete_after=15,
                ephemeral=True,
            )
            return

        claim_channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
        claim_channels = [
            ctx.guild.get_channel(channel_id) for channel_id in claim_channel_ids
        ]

        if claim_channels and ctx.channel not in claim_channels:
            await ctx.message.delete(delay=15)
            await ctx.reply(
                f"You can only claim your daily {currency_name} in {', '.join([channel.mention for channel in claim_channels])}.",
                ephemeral=True,
                delete_after=10,
            )
            return

        daily_amount = await self.config.guild(ctx.guild).daily_award()

        new_balance = await Points._add_balance(ctx.author, daily_amount)  # type: ignore[arg-type]
        await self.config.user(ctx.author).last_claim_timestamp.set(
            datetime.datetime.now().timestamp()
        )
        await ctx.reply(
            f"Claimed {daily_amount} {currency_name}. Your new balance: `{new_balance}`\nYou can claim again at <t:{int(tomorrow.timestamp())}:F>.",
            delete_after=15,
            ephemeral=True,
        )
        pass

    @points.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def award(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Award points to a user.

        Args:
            user (discord.Member): The user to award points to.
            amount (int): The amount of points to award.
        """
        await Points._add_balance(user, amount)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.reply(f"Awarded {amount} {currency_name} to {user.mention}.")
        pass

    @points.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def take(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Take points from a user.

        Args:
            user (discord.Member): The user to take points from.
            amount (int): The amount of points to take.
        """
        await Points._remove_balance(user, amount)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.reply(f"Taken {amount} {currency_name} from {user.mention}.")
        pass

    @points.command()
    @commands.guild_only()
    @commands.mod_or_permissions(manage_roles=True)
    async def set(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Set a user's points.

        Args:
            user (discord.Member): The user to set points for.
            amount (int): The amount of points to set.
        """
        before = await Points._get_balance(user)
        await Points._set_balance(user, amount)
        await ctx.reply(f"Set {user.mention}'s points from `{before}` --> `{amount}`.")
        pass

    @points.command()
    @commands.guild_only()
    async def balance(
        self, ctx: commands.Context, user: typing.Optional[discord.Member]
    ):
        """Check your points balance.

        Args:
            user (typing.Optional[discord.Member]): The user to check the balance for.
        """
        claim_channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
        claim_channels = [
            ctx.guild.get_channel(channel_id) for channel_id in claim_channel_ids
        ]

        if (
            claim_channels and ctx.channel not in claim_channels
        ) and not ctx.author.guild_permissions.moderate_members:
            await ctx.message.delete(delay=15)
            await ctx.reply(
                f"You can only view the balance in {', '.join([channel.mention for channel in claim_channels])}.",
                ephemeral=True,
                delete_after=10,
            )
            return

        if user is None:
            user = ctx.author
        elif not ctx.author.guild_permissions.moderate_members and user != ctx.author:
            await ctx.reply(
                "You don't have permission to check another user's balance."
            )
            return

        balance = await Points._get_balance(user)  # type: ignore[arg-type]
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]

        account = await bank.get_account(user)  # type: ignore[arg-type]

        description = f"**User**: {user.mention}\n"
        description += f"**Balance**: {balance} {currency_name}\n"
        description += (
            f"**Claimed Daily Award**: {await Points._is_daily_award_claimed(user)}\n"
        )
        description += (
            f"**Leaderboard Position**: {await bank.get_leaderboard_position(user)}\n"
        )
        description += f"**Created At**: {account.created_at.replace(tzinfo=timezone):%Y-%m-%d %H:%M:%S %Z}\n"

        offset = await self.config.guild(ctx.guild).offset()
        max_balance = await bank.get_max_balance(ctx.guild) + offset  # type: ignore[arg-type]

        color = discord.Color.dark_grey()  # Dark Grey
        if balance > 0.8 * max_balance:
            color = discord.Color.from_str("0x941A8D")  # Purple
        elif balance > 0.5 * max_balance:
            color = discord.Color.gold()  # Gold
        elif balance > 0.3 * max_balance:
            color = discord.Color.from_str("0xC0C0C0")  # Silver
        elif balance > 0.1 * max_balance:
            color = discord.Color.from_str("0xB87333")  # Copper

        embed = discord.Embed(
            title=f"{user.name}'s Balance", description=description, color=color
        )
        embed.set_footer(text=f"Requested by {ctx.author.nick or ctx.author.name}")

        if ctx.author.guild_permissions.moderate_members:
            view = BalanceAdjustmentButtons(ctx, user)
        else:
            view = None

        await ctx.reply(embed=embed, view=view)
        pass

    @points.command()
    @commands.cooldown(1, 60, commands.BucketType.channel)
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.Context):
        """Check the points leaderboard."""
        claim_channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
        claim_channels = [
            ctx.guild.get_channel(channel_id) for channel_id in claim_channel_ids
        ]

        if (
            claim_channels and ctx.channel not in claim_channels
        ) and not ctx.author.guild_permissions.moderate_members:
            await ctx.message.delete(delay=15)
            await ctx.reply(
                f"You can only view the leaderboard in {', '.join([channel.mention for channel in claim_channels])}.",
                ephemeral=True,
                delete_after=10,
            )
            return

        leaderboard = await bank.get_leaderboard(100, ctx.guild)  # type: ignore[arg-type]

        description = ""

        offset = await self.config.guild(ctx.guild).offset()

        for i, (user_id, stats) in enumerate(leaderboard):
            user = ctx.guild.get_member(user_id)  # type: ignore[arg-type]
            if user is None:
                user = await self.bot.fetch_user(user_id)
            balance = stats["balance"] + offset
            description += f"{i+1}. {user.mention} - `{balance}`\n"

        bank_name = await bank.get_bank_name(ctx.guild)

        embed = discord.Embed(
            title=f"{bank_name} Leaderboard",
            description=description,
            color=discord.Color.gold(),
        )

        await ctx.reply(embed=embed)
        pass

    @commands.Cog.listener(name="on_message")
    @commands.guild_only()
    async def listen_passive_points_earned(self, message: discord.Message):
        if message.author.bot:
            return

        if not await self.config.guild(message.guild).is_enabled():
            return

        passive_chance = await self.config.guild(message.guild).passive_chance()

        if random.random() > passive_chance:
            return
        
        passive_channel_ids = await self.config.guild(message.guild).passive_channels()
        passive_channels = [
            message.guild.get_channel(channel_id) for channel_id in passive_channel_ids
        ]

        if passive_channel_ids and len(passive_channel_ids) > 0 and message.channel not in passive_channels:
            return

        user = message.author

        last_passive_timestamp = await self.config.user(user).last_passive_timestamp()
        last_passive_time = datetime.datetime.fromtimestamp(
            last_passive_timestamp, tz=timezone
        )

        last_passive_count = await self.config.user(user).last_passive_count()

        if (
            last_passive_time.date() == datetime.datetime.now(tz=timezone).date() and 
            last_passive_count >= await self.config.guild(message.guild).passive_max_count_per_day()
        ):
            return
        
        if last_passive_time.date() != datetime.datetime.now(tz=timezone).date():
            last_passive_count = 0
        
        passive_amount = await self.config.guild(message.guild).passive_award_amount()

        new_balance = await Points._add_balance(user, passive_amount)  # type: ignore[arg-type]

        await self.config.user(user).last_passive_timestamp.set(
            datetime.datetime.now().timestamp()
        )
        await self.config.user(user).last_passive_count.set(last_passive_count + 1)

        passive_responses = await self.config.guild(message.guild).passive_award_responses()

        if passive_responses and len(passive_responses) > 0:
            passive_response = random.choice(passive_responses)
            currency_name = await bank.get_currency_name(message.guild)  # type: ignore[arg-type]
            passive_response = passive_response.replace("$POINTS$", f"`{passive_amount} {currency_name}`")

            await message.reply(f"{passive_response}\nNew Balance: `{new_balance} {currency_name}`")
        pass
