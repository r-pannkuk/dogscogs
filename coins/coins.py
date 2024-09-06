import random
from typing import Literal
import typing
import datetime
import pytz

import discord
from redbot.core import commands, bank
from redbot.core.bot import Red
from redbot.core.config import Config

from .paginated import PaginatedEmbed
from .embed import CoinsPassiveConfigurationView, CoinsPassiveConfigurationEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD = {
    "is_enabled": False,
    "daily_award": 10,
    "daily_award_channels": [],
    "offset": -50000,
    "passive_chance": 0.0750,
    "passive_award_amount": 1,
    "passive_max_count_per_day": 20,
    "passive_channels": [],
    "passive_channels_silent": [],
    "passive_award_responses": [
        "That was a particularly good statement. Here, have $COINS$.",
        "I don't like you, but I can't deny this take. Have $COINS$.",
        "You're not as bad as I thought. Have $COINS$.",
        "Your opinions continue to confuse me. Have $COINS$.",
        "For your loyalty to the server, have $COINS$.",
        "I'm insulted by this take, but I'll give you $COINS$ anyway.",
        "Hazelyn told me to give $COINS$ to the worst poster today. Here you go.",
        "I feel bad that you're constantly getting beat up in the server. Have $COINS$.",
        "I'm sorry for the way you're treated. Have $COINS$.",
        "Every once in a while I feel generous. Have $COINS$. I hope you're happy.",
        "I'm not sure why you're still here, but have $COINS$.",
        "You're not the worst. Have $COINS$.",
        "You need to improve your skills. Maybe $COINS$ can serve as motivation.",
        "Maybe if I give you $COINS$ you'll shut up for once.",
        "You're annoying me. Will $COINS$ make it stop?",
        "On the list of best users in the server, you're name isn't on it. Here's $COINS$ anyway.",
        "Your skills might be a joke, but it makes me laugh. Here's $COINS$.",
    ],
    "passive_response_chance": 0.0666666666667,
    "passive_response_multiplier": 3.0,
    "passive_response_jackpot_chance": 0.2,
    "passive_response_jackpot_multiplier": 5.0,
}

DEFAULT_USER = {
    "last_claim_timestamp": 0,
    "last_passive_timestamp": 0,
    "last_passive_count": 0,
}

LIMIT_PER_PAGE = 5

timezone = pytz.timezone("US/Eastern")

class BalanceEmbed(discord.Embed):
    def __init__(self, config: Config, member: discord.Member):
        self.config = config
        self.member = member
        self.guild = member.guild
        super().__init__(title=f"{self.member.display_name}'s Balance")
        pass

    async def collect(self):
        balance = await Coins._get_balance(self.member)  # type: ignore[arg-type]
        currency_name = await bank.get_currency_name(self.guild)  # type: ignore[arg-type]

        account = await bank.get_account(self.member)  # type: ignore[arg-type]

        description = f"**User**: {self.member.mention} ({self.member.name})\n"
        description += f"**Balance**: {balance} {currency_name}\n"

        last_passive_timestamp = await self.config.user(self.member).last_passive_timestamp()
        last_passive_time = datetime.datetime.fromtimestamp(
            last_passive_timestamp, tz=timezone
        )
        max_passive_claims = await self.config.guild(self.guild).passive_max_count_per_day()
        last_passive_count = await self.config.user(self.member).last_passive_count()

        if last_passive_time.date() != datetime.datetime.now(tz=timezone).date():
            last_passive_count = 0
            await self.config.user(self.member).last_passive_count.set(0)

        description += (
            f"**Daily Claims**: {last_passive_count}/{max_passive_claims}\n"
        )

        if last_passive_count >= max_passive_claims:
            description += f"**Next Passive**: <t:{int((datetime.datetime.now(tz=timezone) + datetime.timedelta(days=1)).replace(hour=0, second=0, minute=0, microsecond=0).timestamp())}:F>\n"

        description += (
            f"**Leaderboard Position**: {await bank.get_leaderboard_position(self.member)}\n"
        )

        offset = await self.config.guild(self.guild).offset()
        max_balance = await bank.get_max_balance(self.guild) + offset  # type: ignore[arg-type]

        color = discord.Color.dark_grey()  # Dark Grey
        if balance > 0.8 * max_balance:
            color = discord.Color.from_str("0x941A8D")  # Purple
        elif balance > 0.5 * max_balance:
            color = discord.Color.gold()  # Gold
        elif balance > 0.3 * max_balance:
            color = discord.Color.from_str("0xC0C0C0")  # Silver
        elif balance > 0.1 * max_balance:
            color = discord.Color.from_str("0xB87333")  # Copper

        self.description=description
        self.color=color
        self.set_footer(text=f"Requested by {self.member.nick or self.member.name}")

        return self


class BalanceAdjustmentButtons(discord.ui.View):
    class _Modal(discord.ui.Modal, title="Placeholder"):
        answer : discord.ui.TextInput = discord.ui.TextInput(label="Answer", style=discord.TextStyle.short)

        def __init__(self, ctx: commands.Context, target: discord.Member):
            super().__init__(timeout=None)
            self.ctx = ctx
            self.target = target

        async def init(self, *, title: str, label: str):
            """Fetch values from the bank."""
            currency_name = await bank.get_currency_name(self.ctx.guild)  # type: ignore[arg-type]
            self.title = title.replace("$COINS$", currency_name)
            self.answer.label = label.replace("$COINS$", currency_name)
            self.answer.required = True

        async def interaction_check(self, interaction: discord.Interaction):
            if not self.answer.value:
                raise commands.BadArgument("You must provide a value.")
            try:
                test = int(self.answer.value)
            except ValueError:
                raise commands.BadArgument(
                    "The value you provided is invalid. Please enter an integer."
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
                title=f"How many $COINS$ to award?",
                label="Amount",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_balance = await Coins._add_balance(self.target, int(self.answer.value))  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Awarded {self.answer.value} to {self.target.mention}. New Balance: `{new_balance}`",
                delete_after=15,
            )

    class TakeModal(_Modal):
        async def init(self):
            await super().init(
                title=f"How many $COINS$ to remove?",
                label="Amount",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_balance = await Coins._remove_balance(self.target, int(self.answer.value))  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Removed {self.target.mention}'s balance by {self.answer.value}. New Balance: `{new_balance}`",
                delete_after=15,
            )

    class SetModal(_Modal):
        async def init(self):
            await super().init(
                title=f"What value to set $COINS$ balance to",
                label=f"Amount",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_balance = await Coins._set_balance(self.target, int(self.answer.value))  # type: ignore[arg-type]
            await interaction.response.send_message(
                f"Set {self.target.mention}'s balance to {new_balance}.",
                delete_after=15,
            )

    class ChangePassive(_Modal):
        def __init__(self, config: Config, ctx: commands.Context, target: discord.Member):
            super().__init__(ctx, target)
            self.config = config

        async def init(self):
            await super().init(
                title=f"Set current Daily Passive Claim",
                label=f"Amount (out of {await self.config.guild(self.target.guild).passive_max_count_per_day()})",
            )

        async def on_submit(self, interaction: discord.Interaction):
            new_passive = await self.config.user(self.target).last_passive_count.set(int(self.answer.value))
            await interaction.response.send_message(
                f"Set {self.target.mention}'s daily passive claim count to {new_passive}.",
                delete_after=15,
            )

    def __init__(self, config: Config, embed_message: discord.Message, ctx: commands.Context, target: discord.Member):
        super().__init__(timeout=None)
        self.config = config
        self.ctx = ctx
        self.embed_message = embed_message
        self.target = target

    @discord.ui.button(label="Add", style=discord.ButtonStyle.green)
    async def award(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_roles:   # type: ignore
            await interaction.response.send_message(
                "You don't have permission to award coins.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.AddModal(self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.embed_message.edit(view=self, embed=await BalanceEmbed(self.config, self.target).collect())

    @discord.ui.button(label="Set", style=discord.ButtonStyle.blurple)
    async def set(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_roles:  # type: ignore
            await interaction.response.send_message(
                "You don't have permission to set coins.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.SetModal(self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.embed_message.edit(view=self, embed=await BalanceEmbed(self.config, self.target).collect())


    @discord.ui.button(label="Remove", style=discord.ButtonStyle.red)
    async def take(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_roles:  # type: ignore
            await interaction.response.send_message(
                "You don't have permission to remove coins.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.TakeModal(self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.embed_message.edit(view=self, embed=await BalanceEmbed(self.config, self.target).collect())

    @discord.ui.button(label="Adjust Daily Count", style=discord.ButtonStyle.grey, row=1)
    async def passive(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.manage_roles:  # type: ignore
            await interaction.response.send_message(
                "You don't have permission to adjust passive claims count.",
                ephemeral=True,
                delete_after=10,
            )
            return
        modal = self.ChangePassive(self.config, self.ctx, self.target)
        await modal.init()
        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.embed_message.edit(view=self, embed=await BalanceEmbed(self.config, self.target).collect())

class Coins(commands.Cog):
    """
    Manages local guild coins.
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
            cog_name="Coins",
            identifier=260288776360820736,
            force_registration=True,
        )
        offset = await config.guild(user.guild).offset()
        current_balance = await Coins._get_balance(user)
        max_balance = await bank.get_max_balance(user.guild)  # type: ignore[arg-type]
        if current_balance + amount - offset > max_balance:
            amount = max_balance - current_balance + offset
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
            cog_name="Coins",
            identifier=260288776360820736,
            force_registration=True,
        )
        offset = await config.guild(user.guild).offset()
        # current_balance = await Coins._get_balance(user)
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
            cog_name="Coins",
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
            cog_name="Coins",
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
            cog_name="Coins",
            identifier=260288776360820736,
            force_registration=True,
        )
        offset = await config.guild(user.guild).offset()
        return await bank.get_balance(user) + offset
    
    @staticmethod
    async def _get_currency_name(guild: discord.Guild) -> str:
        """Get the local currency name.

        Args:
            guild (discord.Guild): The guild to get the currency name for.

        Returns:
            str: The local currency name.
        """
        return await bank.get_currency_name(guild)  # type: ignore[arg-type]

    @commands.group()
    async def coins(self, ctx: commands.Context):
        """Manage local guild coins."""
        pass

    @coins.group()
    @commands.has_guild_permissions(manage_roles=True)
    async def settings(self, ctx: commands.Context):
        """Manage local guild coins settings."""
        pass

    @settings.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def enable(self, ctx: commands.Context):
        """Enable coins in this guild."""
        await self.config.guild(ctx.guild).is_enabled.set(True)
        await ctx.send("Coins `ENABLED`.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def disable(self, ctx: commands.Context):
        """Disable coins in this guild."""
        await self.config.guild(ctx.guild).is_enabled.set(False)
        await ctx.send("Coins `DISABLED`.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.Context, bool: typing.Optional[bool]):
        """Check or set if coins are enabled in this guild.

        Args:
            bool (typing.Optional[bool]): Set if coins are enabled or not.
        """
        if bool is None:
            bool = await self.config.guild(ctx.guild).is_enabled()

        await self.config.guild(ctx.guild).is_enabled.set(bool)
        await ctx.send(f"Coins are {'`ENABLED`' if bool else '`DISABLED`'}.")
        pass

    @settings.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
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
    @commands.has_guild_permissions(manage_roles=True)
    async def name(self, ctx: commands.Context):
        """Manage the naming settings."""
        pass

    @name.command(name="bank")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
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
    @commands.has_guild_permissions(manage_roles=True)
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
    @commands.has_guild_permissions(manage_roles=True)
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
    @commands.has_guild_permissions(manage_roles=True)
    async def daily(self, ctx: commands.Context):
        """Manage daily award settings."""
        pass

    # @daily.command(name="amount")
    # @commands.guild_only()
    # @commands.has_guild_permissions(manage_roles=True)
    # async def daily_amount(self, ctx: commands.Context, int: typing.Optional[int]):
    #     """Set the daily award for a user.

    #     Args:
    #         int (typing.Optional[int]): The daily award for a user.
    #     """
    #     if int is None:
    #         int = await self.config.guild(ctx.guild).daily_award()

    #     await self.config.guild(ctx.guild).daily_award.set(int)
    #     await ctx.send(f"The daily award is set to `{int}`.")
    #     pass

    @daily.command(name="channels", aliases=["channel"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def daily_channels(
        self, ctx: commands.GuildContext, *channels: discord.TextChannel
    ):
        """Set the channels where the daily award can be claimed.

        Args:
            channels (discord.TextChannel): The channels where the daily award can be claimed.
        """
        if not channels:
            channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
            channels = [ctx.guild.get_channel(channel_id) for channel_id in channel_ids] #type: ignore
            channels = [channel for channel in channels if channel is not None]  # type: ignore
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
    @commands.has_guild_permissions(manage_roles=True)
    async def passive(self, ctx: commands.Context):
        """Manages passive point generation settings."""
        pass

    @passive.command(name="config")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def passive_config(
        self, ctx: commands.GuildContext
    ):
        """View the passive point generation configuration."""
        embed = await CoinsPassiveConfigurationEmbed(self.bot, self.config, ctx.guild).collect()
        message = await ctx.send(embed=embed)
        view = CoinsPassiveConfigurationView(self.bot, self.config, message, ctx.author)
        await message.edit(embed=embed, view=view, delete_after=60*10)
        pass

    @passive.group(name="response", aliases=["responses"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def passive_response(self, ctx: commands.Context):
        """If triggered, the user will receive a bonus and a response will trigger."""
        pass

    @passive_response.command(name="add")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def passive_response_add(self, ctx: commands.Context, *, response: str):
        """Add a passive point generation response.  Use `$COINS$` to represent the amount of coins awarded.

        Args:
            response (str): The response to add.
        """
        responses = await self.config.guild(ctx.guild).passive_award_responses()
        responses.append(response)
        await self.config.guild(ctx.guild).passive_award_responses.set(responses)
        await ctx.send(f"Added response: `{response}`.")
        pass

    @passive_response.command(name="remove")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def passive_response_remove(self, ctx: commands.Context, index: int):
        """Remove a passive point generation response.

        Args:
            index (int): The index of the response to remove.
        """
        responses = await self.config.guild(ctx.guild).passive_award_responses()
        if index < 1 or index > len(responses):
            await ctx.send("Invalid index.")
            return

        response = responses.pop(index - 1)
        await self.config.guild(ctx.guild).passive_award_responses.set(responses)
        await ctx.send(f"Removed response: `{response}`.")
        pass

    @passive_response.command(name="list")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def passive_response_list(self, ctx: commands.Context):
        """List all passive point generation responses."""
        responses = await self.config.guild(ctx.guild).passive_award_responses()
        if len(responses) == 0:
            await ctx.send("No responses.")
            return

        response_list = "\n".join(
            [f"{i+1}. {response}" for i, response in enumerate(responses)]
        )
        await ctx.send(f"Responses:\n{response_list}")
        pass

    # @coins.command()
    # @commands.guild_only()
    # async def claim(self, ctx: commands.GuildContext):
    #     """Claim your daily coins."""
    #     tomorrow = (
    #         datetime.datetime.now(tz=timezone) + datetime.timedelta(days=1)
    #     ).replace(hour=0, minute=0, second=0, microsecond=0)
    #     currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]

    #     if await Coins._is_daily_award_claimed(ctx.author):
    #         await ctx.reply(
    #             f"You have already claimed your daily {currency_name}. Try again at <t:{int(tomorrow.timestamp())}:F>.",
    #             delete_after=15,
    #             ephemeral=True,
    #         )
    #         return

    #     claim_channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
    #     claim_channels = [
    #         ctx.guild.get_channel(channel_id) for channel_id in claim_channel_ids
    #     ]

    #     if claim_channels and ctx.channel not in claim_channels:
    #         await ctx.message.delete(delay=15)
    #         await ctx.reply(
    #             f"You can only claim your daily {currency_name} in {', '.join([channel.mention for channel in claim_channels])}.",  # type: ignore
    #             ephemeral=True,
    #             delete_after=10,
    #         )
    #         return

    #     daily_amount = await self.config.guild(ctx.guild).daily_award()

    #     new_balance = await Coins._add_balance(ctx.author, daily_amount)  # type: ignore[arg-type]
    #     await self.config.user(ctx.author).last_claim_timestamp.set(
    #         datetime.datetime.now().timestamp()
    #     )
    #     await ctx.reply(
    #         f"Claimed {daily_amount} {currency_name}. Your new balance: `{new_balance}`\nYou can claim again at <t:{int(tomorrow.timestamp())}:F>.",
    #         delete_after=15,
    #         ephemeral=True,
    #     )
    #     pass

    @coins.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def award(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Award coins to a user.

        Args:
            user (discord.Member): The user to award coins to.
            amount (int): The amount of coins to award.
        """
        await Coins._add_balance(user, amount)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.reply(f"Awarded {amount} {currency_name} to {user.mention}.")
        pass

    @coins.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def take(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Take coins from a user.

        Args:
            user (discord.Member): The user to take coins from.
            amount (int): The amount of coins to take.
        """
        await Coins._remove_balance(user, amount)
        currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
        await ctx.reply(f"Taken {amount} {currency_name} from {user.mention}.")
        pass

    @coins.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def set(self, ctx: commands.Context, user: discord.Member, amount: int):
        """Set a user's coins.

        Args:
            user (discord.Member): The user to set coins for.
            amount (int): The amount of coins to set.
        """
        before = await Coins._get_balance(user)
        await Coins._set_balance(user, amount)
        await ctx.reply(f"Set {user.mention}'s coins from `{before}` --> `{amount}`.")
        pass

    @coins.command()
    @commands.guild_only()
    async def balance(
        self, ctx: commands.GuildContext, member: typing.Optional[discord.Member]
    ):
        """Check your coins balance.

        Args:
            user (typing.Optional[discord.Member]): The user to check the balance for.
        """
        claim_channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
        claim_channels = [
            channel
            for channel in [
                ctx.guild.get_channel(channel_id) for channel_id in claim_channel_ids
            ]
            if channel is not None
        ]

        if (
            claim_channels and ctx.channel not in claim_channels
        ) and not ctx.author.guild_permissions.manage_roles:
            await ctx.message.delete(delay=15)
            await ctx.reply(
                f"You can only view the balance in {', '.join([channel.mention for channel in claim_channels])}.",
                ephemeral=True,
                delete_after=10,
            )
            return

        if member is None:
            member = ctx.author
        elif not ctx.author.guild_permissions.manage_roles and member != ctx.author:
            await ctx.reply(
                "You don't have permission to check another user's balance."
            )
            return
        
        embed = await BalanceEmbed(self.config, member).collect()

        embed_message : discord.Message = await ctx.reply(embed=embed)
        
        if ctx.author.guild_permissions.manage_roles:
            view = BalanceAdjustmentButtons(self.config, embed_message, ctx, member)
        else:
            view = None

        await embed_message.edit(embed=embed, view=view)

        pass

    @coins.command()
    @commands.cooldown(1, 60, commands.BucketType.channel)
    @commands.guild_only()
    async def leaderboard(self, ctx: commands.GuildContext):
        """Check the coins leaderboard."""
        claim_channel_ids = await self.config.guild(ctx.guild).daily_award_channels()
        claim_channels = [
            ctx.guild.get_channel(channel_id) for channel_id in claim_channel_ids
        ]

        if (
            claim_channels and ctx.channel not in claim_channels
        ) and not ctx.author.guild_permissions.manage_roles:
            await ctx.message.delete(delay=15)
            await ctx.reply(
                f"You can only view the leaderboard in {', '.join([channel.mention for channel in claim_channels])}.",  # type: ignore
                ephemeral=True,
                delete_after=10,
            )
            return

        leaderboard = await bank.get_leaderboard(100, ctx.guild)  # type: ignore[arg-type]

        bank_name = await bank.get_bank_name(ctx.guild)
        balance_offset = await self.config.guild(ctx.guild).offset()

        async def get_page(page: int):
            embed = discord.Embed(
                title=f"{bank_name} Leaderboard",
                color=discord.Color.gold(),
                description=""
            )
            offset = page * LIMIT_PER_PAGE

            for i, (user_id, stats) in enumerate(leaderboard[offset:offset + LIMIT_PER_PAGE]):
                user = ctx.guild.get_member(user_id)  # type: ignore[arg-type]
                if user is None:
                    user = await self.bot.fetch_user(user_id)  # type: ignore
                balance = stats["balance"] + balance_offset
                embed.description += f"{i+1+offset}. {user.mention} - `{balance}`\n"  # type: ignore

            n = PaginatedEmbed.compute_total_pages(len(leaderboard), LIMIT_PER_PAGE)
            embed.set_footer(text=f"Page {page+1}/{n}")
            return embed, n

        await PaginatedEmbed(message=ctx.message, get_page=get_page).send() # type: ignore
        pass

    @commands.Cog.listener(name="on_message")
    @commands.guild_only()
    async def listen_passive_coins_earned(self, message: discord.Message):
        if message.author.bot:
            return

        if not message.guild:
            return

        if not await self.config.guild(message.guild).is_enabled():
            return

        passive_chance = await self.config.guild(message.guild).passive_chance()

        roll = random.random()

        if roll > passive_chance:
            return

        normal_passive_channel_ids = await self.config.guild(message.guild).passive_channels()
        silent_passive_channel_ids = await self.config.guild(message.guild).passive_channels_silent()
        combined_passive_channel_ids = normal_passive_channel_ids + silent_passive_channel_ids

        if (
            combined_passive_channel_ids
            and len(combined_passive_channel_ids) > 0
            and message.channel.id not in combined_passive_channel_ids
        ):
            return

        user = message.author

        last_passive_timestamp = await self.config.user(user).last_passive_timestamp()
        last_passive_time = datetime.datetime.fromtimestamp(
            last_passive_timestamp, tz=timezone
        )

        last_passive_count = await self.config.user(user).last_passive_count()

        if (
            last_passive_time.date() == datetime.datetime.now(tz=timezone).date()
            and last_passive_count
            >= await self.config.guild(message.guild).passive_max_count_per_day()
        ):
            return

        if last_passive_time.date() != datetime.datetime.now(tz=timezone).date():
            last_passive_count = 0

        passive_amount = await self.config.guild(message.guild).passive_award_amount()

        passive_response_chance = await self.config.guild(
            message.guild
        ).passive_response_chance()

        passive_jackpot_chance = await self.config.guild(
            message.guild
        ).passive_response_jackpot_chance()

        await self.config.user(user).last_passive_timestamp.set(
            datetime.datetime.now().timestamp()
        )
        await self.config.user(user).last_passive_count.set(last_passive_count + 1)

        currency_name = await bank.get_currency_name(message.guild)  # type: ignore[arg-type]

        if not message.channel.id in silent_passive_channel_ids:
            await message.add_reaction("🪙")

        if roll <= passive_response_chance * passive_chance:
            if roll <= passive_jackpot_chance * passive_response_chance * passive_chance:
                passive_amount *= int(await self.config.guild(message.guild).passive_response_jackpot_multiplier())
            else:
                passive_amount *= int(await self.config.guild(message.guild).passive_response_multiplier())

        new_balance = await Coins._add_balance(user, passive_amount)  # type: ignore[arg-type]

        if roll <= passive_response_chance * passive_chance:
            passive_responses = await self.config.guild(
                message.guild
            ).passive_award_responses()

            if passive_responses and len(passive_responses) > 0:
                passive_response = random.choice(passive_responses)
                passive_response = passive_response.replace(
                    "$COINS$", f"`{passive_amount} {currency_name}`"
                )

            message_reply = f"{passive_response}\n"
            message_reply += f"New Balance: `{new_balance} {currency_name}`"

            if not message.channel.id in silent_passive_channel_ids:
                await message.reply(message_reply, delete_after=20)

        pass


def consume_coins(cost: int):
    async def predicate(ctx: commands.GuildContext):
        if not await bank.can_spend(ctx.author, cost):
            currency_name = await bank.get_currency_name(ctx.guild)  # type: ignore[arg-type]
            await ctx.reply(
                f"You don't have enough {currency_name} to use this command.",
                delete_after=15,
                ephemeral=True,
            )
            return False
        
        await bank.withdraw_credits(ctx.author, cost)
        return True

    return commands.check(predicate)