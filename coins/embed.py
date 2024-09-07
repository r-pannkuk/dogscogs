import abc
import typing
import discord
from redbot.core.config import Config
from redbot.core import bank
from redbot.core.bot import Red

from utils.converters import PercentageOrFloat

class CoinsPassiveConfigurationEmbed(discord.Embed):
    def __init__(self, client: Red, config: Config, guild: discord.Guild):
        super().__init__(
            title=f"Coins Passive Award Configuration", color=discord.Color.gold()
        )

        self.config = config
        self.client = client
        self.guild = guild
        self.group = config.guild(guild)

    async def collect(self):
        self.currency_name = await bank.get_currency_name(self.guild)
        # self.is_enabled = await self.group.is_enabled()
        # self.daily_award = await self.group.daily_award()
        # self.daily_award_channels = await self.group.daily_award_channels()
        self.passive_max = await self.group.passive_max_count_per_day()
        self.passive_chance = await self.group.passive_chance()
        self.passive_award_amount = await self.group.passive_award_amount()
        self.passive_channel_ids = await self.group.passive_channels()
        self.passive_channel_silent_ids = await self.group.passive_channels_silent()
        self.passive_channels = [
            (c, False)
            for c in [
                self.guild.get_channel(channel_id)
                for channel_id in self.passive_channel_ids
            ]
            if c is not None
        ] + [
            (c, True)
            for c in [
                self.guild.get_channel(channel_id)
                for channel_id in self.passive_channel_silent_ids
            ]
            if c is not None
        ]
        self.passive_award_responses = await self.group.passive_award_responses()
        self.passive_response_chance = await self.group.passive_response_chance()
        self.passive_response_multiplier = (
            await self.group.passive_response_multiplier()
        )
        self.passive_response_jackpot_chance = (
            await self.group.passive_response_jackpot_chance()
        )
        self.passive_response_jackpot_multiplier = (
            await self.group.passive_response_jackpot_multiplier()
        )

        self.description = f"The below configuration will be used to passively award {self.currency_name}:\n"

        channel_string = ", ".join(
            [
                mention
                for mention in [
                    f"{c.mention}{' (Silent)' if silent else ''}"
                    for c, silent in self.passive_channels
                    if silent == True
                    or c not in [c for c, silent in self.passive_channels if silent == True]
                ]
            ]
        )

        if channel_string is None or channel_string == "":
            channel_string = "All"

        self.add_field(
            name="Passive Award",
            value=f"__Passive Award Chance__: {self.passive_chance:,.2%}\n"
            + f"__Triggering Channels__: {channel_string}\n"
            + f"__Passive Award Amount__: {self.passive_award_amount}\n"
            + f"__Max Awards Per Day__: {self.passive_max}\n",
            inline=False,
        )

        responses_string = ":coin:"
        i = 0
        if len(self.passive_award_responses) > 0:
            i += 1
            responses_string = f"\n  {i}. ".join(self.passive_award_responses)

        self.add_field(
            name="Bonus Trigger",
            value=f"__Bonus Chance__: {self.passive_response_chance:,.2%} of award messages ({self.passive_response_chance * self.passive_chance:,.2%} overall)\n"
            + f"__Bonus Multiplier__: {self.passive_response_multiplier}x ({int(self.passive_response_multiplier * self.passive_award_amount)} {self.currency_name})\n"
            + f"__Bonus Responses__: {f'See `{(await self.client.get_valid_prefixes(self.guild))[0]}coins settings passive response list`' if len(responses_string) > 800 else responses_string}\n",
            inline=False,
        )

        self.add_field(
            name="Jackpot Trigger",
            value=f"__Jackpot Chance__: {self.passive_response_jackpot_chance:,.2%} of bonus messages ({self.passive_response_chance * self.passive_response_jackpot_chance * self.passive_chance:,.2%} overall)\n"
            + f"__Jackpot Multiplier__: {self.passive_response_jackpot_multiplier}x ({int(self.passive_response_jackpot_multiplier * self.passive_award_amount)} {self.currency_name})\n",
            inline=False,
        )

        return self


class NumberPromptModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        author: typing.Union[discord.Member, discord.User],
        title: str,
        label: str,
        placeholder: str,
        custom_id: str,
        min: int,
        max: int,
        row: int = 0,
    ):
        super().__init__(
            timeout=10 * 60,
            title=title,
        )

        self.item: discord.ui.TextInput = discord.ui.TextInput(
            label=label,
            placeholder=placeholder,
            required=True,
            style=discord.TextStyle.short,
            custom_id=custom_id,
            row=row,
        )

        self.add_item(self.item)

        self.min = min
        self.max = max
        self.author = author

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.author:
            return False

        try:
            value = PercentageOrFloat.to_float_or_percentage(self.item.value)
        except:
            raise ValueError("Please enter a valid number.")

        if value < self.min or value > self.max:
            raise ValueError(
                f"Please enter a number between {self.min} and {self.max}."
            )

        return True

    async def on_error(self, interaction: discord.Interaction, exception: Exception) -> None:  # type: ignore
        await interaction.response.send_message(
            str(exception), ephemeral=True, delete_after=20
        )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()


class _ConfigurationView(abc.ABC, discord.ui.View):
    def __init__(
        self,
        client: Red,
        config: Config,
        embed_message: discord.Message,
        author: typing.Union[discord.Member, discord.User],
    ):
        self.embed_message = embed_message
        self.author = author
        self.client = client
        self.config = config
        self.guild = embed_message.guild

        super().__init__(timeout=10 * 60)


class CoinsPassiveConfigurationView(_ConfigurationView):
    @discord.ui.button(label="Edit Chance", style=discord.ButtonStyle.secondary, row=0)
    async def edit_base_chance(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="New Trigger Chance",
            label="Base Chance %",
            placeholder=f"{(await self.config.guild(self.guild).passive_chance()) * 100}%",  # type: ignore
            custom_id="edit_passive_chance",
            min=0,
            max=1,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_chance.set(PercentageOrFloat.to_float_or_percentage(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )

    @discord.ui.button(label="Edit Award", style=discord.ButtonStyle.secondary, row=0)
    async def edit_award_amount(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="New Base Award Amount",
            label="Award Amount",
            placeholder=f"{int(await self.config.guild(self.guild).passive_award_amount())}",  # type: ignore
            custom_id="edit_passive_award_amount",
            min=0,
            max=1000000,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_award_amount.set(int(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )

    @discord.ui.button(
        label="Edit Daily Limit", style=discord.ButtonStyle.secondary, row=0
    )
    async def edit_max_awards(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="Max Daily Passive Awards",
            label="Max Awards per Day",
            placeholder=f"{int(await self.config.guild(self.guild).passive_max_count_per_day())}",  # type: ignore
            custom_id="edit_passive_max",
            min=0,
            max=1000000,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_max_count_per_day.set(int(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select Channels",
        custom_id="edit_passive_channels",
        min_values=0,
        max_values=25,
        channel_types=[discord.ChannelType.text],
        row=1,
    )
    async def edit_channels(
        self, interaction: discord.Interaction, select: discord.ui.ChannelSelect
    ):
        if interaction.user != self.author:
            return

        channels = [c.id for c in [self.guild.get_channel(v.id) for v in select.values] if c is not None]  # type: ignore
        await self.config.guild(self.guild).passive_channels.set(channels)  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )
        await interaction.response.defer()

    @discord.ui.select(
        cls=discord.ui.ChannelSelect,
        placeholder="Select Channels (Silent)",
        custom_id="edit_passive_channels_silent",
        min_values=0,
        max_values=25,
        channel_types=[discord.ChannelType.text],
        row=2,
    )
    async def edit_channels_silent(
        self, interaction: discord.Interaction, select: discord.ui.ChannelSelect
    ):
        if interaction.user != self.author:
            return

        channels = [c.id for c in [self.guild.get_channel(v.id) for v in select.values] if c is not None]  # type: ignore
        await self.config.guild(self.guild).passive_channels_silent.set(channels)  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )
        await interaction.response.defer()

    @discord.ui.button(
        label="Edit Bonus Chance", style=discord.ButtonStyle.secondary, row=3
    )
    async def edit_bonus_chance(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="Chance of Bonus Triggering",
            label="Bonus Chance %",
            placeholder=f"{(await self.config.guild(self.guild).passive_response_chance())* 100}%",  # type: ignore
            custom_id="edit_passive_response_chance",
            min=0,
            max=1,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_response_chance.set(PercentageOrFloat.to_float_or_percentage(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )

    @discord.ui.button(
        label="Edit Bonus Multiplier", style=discord.ButtonStyle.secondary, row=3
    )
    async def edit_bonus_multiplier(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="Bonus Award Multiplier",
            label="Bonus Multiplier",
            placeholder=f"{await self.config.guild(self.guild).passive_response_multiplier()}",  # type: ignore
            custom_id="edit_passive_response_multiplier",
            min=1,
            max=1000000,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_response_multiplier.set(float(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )

    @discord.ui.button(
        label="Edit Jackpot Chance", style=discord.ButtonStyle.secondary, row=4
    )
    async def edit_jackpot_chance(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="Chance of Bonus Jackpot Triggering",
            label="Jackpot Chance %",
            placeholder=f"{(await self.config.guild(self.guild).passive_response_jackpot_chance())*100}%",  # type: ignore
            custom_id="edit_passive_response_jackpot_chance",
            min=0,
            max=1,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_response_jackpot_chance.set(PercentageOrFloat.to_float_or_percentage(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )

    @discord.ui.button(
        label="Edit Jackpot Multiplier", style=discord.ButtonStyle.secondary, row=4
    )
    async def edit_jackpot_multiplier(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        if interaction.user != self.author:
            return

        modal = NumberPromptModal(
            author=self.author,
            title="Jackpot Bonus Award Multiplier",
            label="Jackpot Multiplier",
            placeholder=f"{await self.config.guild(self.guild).passive_response_jackpot_multiplier()}",  # type: ignore
            custom_id="edit_passive_response_jackpot_multiplier",
            min=1,
            max=1000000,
        )

        await interaction.response.send_modal(modal)
        await modal.wait()
        await self.config.guild(self.guild).passive_response_jackpot_multiplier.set(float(modal.item.value))  # type: ignore
        await self.embed_message.edit(
            embed=await CoinsPassiveConfigurationEmbed(
                self.client, self.config, self.guild  # type: ignore
            ).collect()
        )
