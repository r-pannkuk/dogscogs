import asyncio
from datetime import datetime, timedelta
import io
import time
import typing
import uuid
import discord
from discord.ext import tasks
from discord.ui.item import Item
from redbot.core import commands
from redbot.core.config import Config

from dogscogs.constants import TIMEZONE
from dogscogs.views.prompts import NumberPromptTextInput, NumberPromptModal
from dogscogs.views.confirmation import ConfirmationView
from dogscogs.views.paginated import PaginatedEmbed
from dogscogs.constants.discord.views import MAX_SELECT_OPTIONS as DISCORD_MAX_SELECT_OPTIONS

from coins import Coins

from .bets import DEFAULT_BET_DESCRIPTION, DEFAULT_BET_TITLE
from .config import BetConfig, BetOption, BetState, Better
from .embed import BetEmbed

REFRESH_INTERVAL = 10
MAX_WINNERS_DISPLAY_LENGTH = 3

class OnCallbackSelect(discord.ui.Select):
    on_callback : typing.Callable[[typing.List[str]], typing.Awaitable[None]]

    def __init__(
        self,
        *args,
        callback: typing.Callable[[typing.List[str]], typing.Awaitable[None]],
        **kwargs
    ):
        self.on_callback = callback
        super().__init__(*args, **kwargs)

    async def callback(self, interaction: discord.Interaction,) -> None:
        await self.on_callback(self.values)
        await interaction.response.defer()

class BetListPaginatedEmbed(PaginatedEmbed):
    config : Config
    ctx : commands.GuildContext
    guild : discord.Guild

    bet_config : BetConfig
    
    def __init__(
            self,
            *args,
            config: Config,
            ctx: commands.GuildContext,
            filter: typing.Callable[[BetConfig], bool] = lambda x: x['state'] in ['open', 'closed', 'config'],
            **kwargs
        ):

        self.config = config
        self.ctx = ctx
        self.guild = ctx.guild 
        self.filter = filter

        async def get_page(index: int) -> typing.Tuple[discord.Embed, int]:
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            bet_configs = list(active_bets.values())
            filtered_configs = [config for config in bet_configs if self.filter(config)]

            if not filtered_configs:
                return discord.Embed(
                    title="No Bets Found",
                    description="No bets were found with the given filter.",
                    color=discord.Color.red()
                ), 0

            self.bet_config = filtered_configs[index]

            return await BetEmbed(
                config=self.config,
                ctx=self.ctx,
                bet_config_id=self.bet_config['id']
            ).generate(), len(filtered_configs)
        
        super().__init__(*args, message=ctx.message, interaction=ctx.interaction, get_page=get_page, **kwargs)

    async def send(self) -> None:
        await super().send()

        _, size = await self.get_page(0)

        if size > 1 and size < DISCORD_MAX_SELECT_OPTIONS:
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            bet_configs = list(active_bets.values())
            filtered_configs = [config for config in bet_configs if self.filter(config)]

            async def edit_selected_page(values: typing.List[str]) -> None:
                self.index = int(values[0])
                await self.edit_page()

            self.bet_list_select : OnCallbackSelect = OnCallbackSelect(
                custom_id="bet_list",
                placeholder="Select a bet to view.",
                options=[
                    discord.SelectOption(
                        label=config['title'],
                        value=str(i),
                        description=f"[{config['state'].capitalize()}] " + (
                            f" || Edited: {datetime.fromtimestamp(config['last_edited_at'], tz=TIMEZONE).strftime('%m-%d-%Y %I:%M %p (%Z)')}" if config['last_edited_at'] is not None else \
                            f" || Created: {datetime.fromtimestamp(config['created_at'], tz=TIMEZONE).strftime('%m-%d-%Y %I:%M %p (%Z)')}"
                        ),
                    )
                    for i, config in enumerate(filtered_configs)
                ],
                callback=edit_selected_page,
                row=1
            )

            self.add_item(self.bet_list_select)
        elif size <= 1:
            self.previous.disabled = True
            self.next.disabled = True

        await self.edit_page()


    async def edit_page(self) -> None:
        await super().edit_page()
        await self.message.edit(content=f"Found {self.total_pages} Bets.\n`{self.index + 1}/{self.total_pages}`", view=self)

    @discord.ui.button(label="Re-Generate", style=discord.ButtonStyle.primary, row=2)
    async def regenerate(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.message.edit(content=None, view=None)
        await interaction.response.defer()
        self.stop()

class ChooseWinnerSelect(discord.ui.Select):
    def __init__(self, *args, parent_view: discord.ui.View, bet_config : BetConfig, **kwargs):
        super().__init__(*args, **kwargs)
        self.bet_config = bet_config
        self.parent_view = parent_view
        options = [
            discord.SelectOption(label=option['option_name'], value=str(option['id']))
            for option in bet_config['options']
        ]
        self.options = options


    async def callback(self, interaction: discord.Interaction) -> None:
        confirmation_view = ConfirmationView(author=interaction.user) # type: ignore[arg-type]
        chosen_options = [self.bet_config['options'][int(value)]['option_name'] for value in self.values]
        await interaction.response.send_message(f"Choosing: `{'`, `'.join(chosen_options)}`\nAre you sure?", ephemeral=True, view=confirmation_view)

        if await confirmation_view.wait():
            return
        
        if confirmation_view.value:
            self.bet_config['winning_option_id'] = int(self.values[0])

        confirmation_view.stop()
        await interaction.delete_original_response()
        self.parent_view.stop()

        pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.bet_config['author_id']:
            await interaction.response.send_message("❌ ERROR: You are not the author of this bet.", ephemeral=True, delete_after=5)
            return False
        return True
    
class ChooseWinnerView(discord.ui.View):
    def __init__(self, *args, bet_config: BetConfig, **kwargs):
        super().__init__(*args, **kwargs)

        self.select_winner = ChooseWinnerSelect(bet_config=bet_config, parent_view=self)
        self.add_item(self.select_winner)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return True

class BetAdministrationConfigModal(discord.ui.Modal):
    bet_config : BetConfig
    is_data_changed : bool = False

    def __init__(
        self, 
        *args,
        bet_config: BetConfig,
        started: bool = False, 
        **kwargs
    ):
        super().__init__(*args, title="Configure Bet Pool", **kwargs)
        self.bet_config = bet_config

        if self.bet_config['title'] == DEFAULT_BET_TITLE:
            self.bet_config['title'] = ""
        if self.bet_config['description'] == DEFAULT_BET_DESCRIPTION:
            self.bet_config['description'] = ""

        self.bet_title : discord.ui.TextInput = discord.ui.TextInput(
            custom_id="title", 
            label="Bet Title",
            placeholder="Title Goes Here",
            default=bet_config['title'],
            row=0,
            required=True,
            style=discord.TextStyle.short
        )

        self.bet_description : discord.ui.TextInput = discord.ui.TextInput(
            custom_id="description", 
            label="Bet Description",
            placeholder="A bet between foes...",
            default=bet_config['description'],
            row=1,
            required=False,
            style=discord.TextStyle.long
        )

        self.bet_minimum : NumberPromptTextInput = NumberPromptTextInput(
            custom_id="minimum", 
            label="Minimum Bet",
            placeholder=str(bet_config['minimum_bet']) or "1",
            row=2,
            required=False,
            style=discord.TextStyle.short,
            min=1,
        )

        self.bet_options : discord.ui.TextInput = discord.ui.TextInput(
            custom_id="options", 
            label="Bet Options",
            placeholder="Option 1, Option 2, Option 3...",
            default=", ".join([option['option_name'] for option in bet_config['options']]),
            row=3,
            required=True,
            style=discord.TextStyle.long,
        )

        self.add_item(self.bet_title)
        self.add_item(self.bet_description)

        if not started:
            self.add_item(self.bet_minimum)
            self.add_item(self.bet_options)

    def _get_options(self) -> typing.List[str]:
        return [option.strip().strip("\"\'") for option in self.bet_options.value.split(',')]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        parsed_options = self._get_options()

        if len(parsed_options) < 2:
            await interaction.response.send_message("You must have at least 2 options.", ephemeral=True, delete_after=5)
            return False
        
        distinct_options = set(parsed_options)

        if len(distinct_options) != len(parsed_options):
            await interaction.response.send_message("❌ ERROR: Options must be distinct.", ephemeral=True, delete_after=5)
            return False
        
        return True
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.bet_config['title'] = self.bet_title.value.strip().strip("\"\'")
        self.bet_config['description'] = self.bet_description.value.strip().strip("\"\'")
        
        if self.bet_minimum.value.isnumeric():
            self.bet_config['minimum_bet'] = int(self.bet_minimum.value)

        self.bet_config['options'] = [{"id": i, "option_name": option} for i, option in enumerate(self._get_options())]

        await interaction.response.send_message("Bet configuration updated.", ephemeral=True, delete_after=5)
        self.is_data_changed = True
        self.stop()

    async def on_error(self, interaction: discord.Interaction, exception: Exception) -> None: # type: ignore
        await interaction.response.send_message(str(exception), ephemeral=True, delete_after=15)

    async def on_cancel(self, interaction: discord.Interaction) -> None:
        self.stop()

class BetButton(discord.ui.Button):
    guild: discord.Guild
    config : Config
    bet_config_id : int
    option_id : int

    def __init__(
            self, 
            *args,
            guild: discord.Guild,
            config: Config,
            bet_config_id: int,
            option_id: int,
            callback: typing.Optional[typing.Callable[[], typing.Awaitable[None]]],
            **kwargs
        ):
        super().__init__(*args, **kwargs)
        self.guild = guild
        self.config = config
        self.bet_config_id = bet_config_id
        self.option_id = option_id
        self.parent_callback = callback

    async def _get_config(self) -> BetConfig:
        active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
        return active_bets[str(self.bet_config_id)]
    
    def _get_better(self, better_list : typing.List[Better],  member: discord.Member):
        found_betters = [better for better in better_list if better['member_id'] == member.id]
        if len(found_betters) > 1:
            raise ValueError(f"Member {member.id} has multiple bets.")
        
        return found_betters[0] if len(found_betters) == 1 else None
    
    async def _set_config(
            self, 
            *, 
            member: discord.Member,
            amount: int,
        ) -> None:
        async with self.config.guild(member.guild).active_bets.get_lock():
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(member.guild).active_bets()
            config = active_bets[str(self.bet_config_id)]

            better : Better = self._get_better(config['betters'], member)

            if better is None:
                better = {
                    'member_id': member.id,
                    'bet_option_id': self.option_id,
                    'bet_amount': 0
                }
            else:
                config['betters'].remove(better)

            better['bet_amount'] += amount

            config['betters'].append(better)

            active_bets.update({str(self.bet_config_id): config})
            
            await self.config.guild(self.guild).active_bets.set(active_bets)

    async def callback(self, interaction: discord.Interaction) -> None:
        config = await self._get_config()
        balance = await Coins._get_balance(interaction.user) # type: ignore[arg-type]

        modal = NumberPromptModal(
            custom_id="bet_amount",
            title="Place Bet",
            author=interaction.user,
            min=config['minimum_bet'] or 1,
            max=balance,
            label="Bet Amount",
            placeholder=f"Enter the amount to bet. (Balance: {balance})",
        )

        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        amount = int(modal.item.value)

        if amount == 0:
            return

        await self._set_config(member=interaction.user, amount=int(modal.item.value)) # type: ignore[arg-type]

        await Coins._remove_balance(interaction.user, amount) # type: ignore[arg-type]

        better = self._get_better((await self._get_config())['betters'], interaction.user) # type: ignore[arg-type]

        await interaction.followup.send(f"💰 You have placed a bet of `{amount}` on `{config['options'][self.option_id]['option_name']}` (Total: `{better['bet_amount']}`)", ephemeral=True)
        
        if self.parent_callback is not None:
            await self.parent_callback()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        config = await self._get_config()
        existing_bet = self._get_better(config['betters'], interaction.user) # type: ignore[arg-type]

        if config['state'] != 'open':
            raise Exception("Betting is not currently open.")

        if existing_bet is not None and existing_bet['bet_option_id'] != self.option_id:
            found_option = next((option for option in config['options'] if option['id'] == existing_bet['bet_option_id']), None)

            if found_option is None:
                raise ValueError(f"Option `{existing_bet['bet_option_id']}` not found.")
            
            raise Exception(f"You have already placed a bet on `{found_option['option_name']}`")
        
        balance = await Coins._get_balance(interaction.user) # type: ignore[arg-type]

        if balance < config['minimum_bet']:
            raise Exception(f"You don't have enough coins in your balance to place a bet.\nMinimum: `{config['minimum_bet']}`\nBalance: `{balance}`")
    
        return True

class BetAdministrationView(discord.ui.View):
    ctx: commands.GuildContext
    original_message: discord.Message
    guild : discord.Guild
    config : Config
    bet_config_id : int
    is_configed : bool = False
    last_update_timestamp : float = 0

    def __init__(
            self, 
            *args,
            ctx: commands.GuildContext, 
            original_message: discord.Message,
            config: Config, 
            bet_config_id: int,
            **kwargs
        ):
        super().__init__(timeout=60*10, *args, **kwargs)

        self.ctx = ctx
        self.original_message = original_message
        self.guild = ctx.guild
        self.config = config
        self.bet_config_id = bet_config_id

        self.edit_config.custom_id = f"edit_config:{self.bet_config_id}"
        self.toggle_open.custom_id = f"toggle_open:{self.bet_config_id}"
        self.resolve.custom_id = f"resolve:{self.bet_config_id}"
        self.cancel.custom_id = f"cancel:{self.bet_config_id}"
        self.add_pool.custom_id = f"add_pool:{self.bet_config_id}"
        self.check_bet.custom_id = f"check_bet:{self.bet_config_id}"
        self.list_winners.custom_id = f"list_winners:{self.bet_config_id}"

        pass

    async def _get_config(self) -> BetConfig:
        active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
        return active_bets[str(self.bet_config_id)]
    
    async def _set_config(
            self, 
            *, 
            title: typing.Optional[str] = None,
            description: typing.Optional[str] = None,
            minimum_bet: typing.Optional[int] = None,
            options: typing.Optional[typing.List[BetOption]] = None,
            state: typing.Optional[BetState] = None,
        ) -> None:
        async with self.config.guild(self.guild).active_bets.get_lock():
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            config = active_bets[str(self.bet_config_id)]

            if title is not None:
                config['title'] = title
            if description is not None:
                config['description'] = description
            if minimum_bet is not None:
                config['minimum_bet'] = minimum_bet
            if options is not None:
                config['options'] = options
            if state is not None:
                config['state'] = state

                if state == 'resolved' or state == 'cancelled':
                    config['closed_at'] = datetime.now().timestamp()

            config['last_edited_at'] = datetime.now().timestamp()

            active_bets.update({str(self.bet_config_id): config})
            
            await self.config.guild(self.guild).active_bets.set(active_bets)
    
    async def generate(self) -> "BetAdministrationView":
        config = await self._get_config()

        if not self.is_configed:
            self.is_configed = config['state'] != 'config'

        self.clear_items()

        if not self.is_configed:
            self.edit_config.disabled = False
            self.toggle_open.disabled = True
            self.resolve.disabled = True
            self.cancel.disabled = False
            self.add_pool.disabled = True
            
            self.add_item(self.edit_config)
            self.add_item(self.toggle_open)
            self.add_item(self.resolve)
            self.add_item(self.cancel)
            self.add_item(self.add_pool)
        else:
            if config['state'] == 'config':
                self.edit_config.disabled = False

                self.toggle_open.disabled = False

                self.resolve.disabled = True

                self.cancel.disabled = False

                self.add_pool.disabled = False

                self.check_bet.disabled = True

                self.list_winners.disabled = True
            if config['state'] == 'open':
                self.edit_config.disabled = False
                
                self.toggle_open.disabled = False
                self.toggle_open.label = "Close"
                self.toggle_open.emoji = discord.PartialEmoji(name="🔒")
                
                self.resolve.disabled = True

                self.cancel.disabled = False

                self.check_bet.disabled = False

                self.list_winners.disabled = True
            elif config['state'] == 'closed':
                self.edit_config.disabled = False

                self.toggle_open.disabled = False
                self.toggle_open.label = "Open"
                self.toggle_open.emoji = discord.PartialEmoji(name="🎰")
                
                self.resolve.disabled = False

                self.cancel.disabled = False

                self.check_bet.disabled = False

                self.list_winners.disabled = True
            elif config['state'] == 'cancelled':
                self.edit_config.disabled = True
                
                self.toggle_open.disabled = True
                
                self.resolve.disabled = True

                self.cancel.disabled = True

                self.add_pool.disabled = True

                self.check_bet.disabled = True

                self.list_winners.disabled = False
            elif config['state'] == 'resolved':
                self.edit_config.disabled = True
                
                self.toggle_open.disabled = True
                
                self.resolve.disabled = True

                self.cancel.disabled = True

                self.add_pool.disabled = True

                self.check_bet.disabled = False

                self.list_winners.disabled = False
            
            self.add_item(self.edit_config)
            self.add_item(self.toggle_open)
            self.add_item(self.resolve)
            self.add_item(self.cancel)
            self.add_item(self.add_pool)

            bet_totals = {option['id']: 0 for option in config['options']}
            for better in config['betters']:
                bet_totals[better['bet_option_id']] += better['bet_amount']

            bet_total = sum(bet_totals.values())

            async def throttled_regenerate():
                current_time = datetime.now().timestamp()
                time_since_last_run = current_time - self.last_update_timestamp

                if time_since_last_run > REFRESH_INTERVAL:
                    await self._regenerate_message()
                    self.last_update_timestamp = current_time
                else:
                    await asyncio.sleep(REFRESH_INTERVAL)

                    current_time = datetime.now().timestamp()
                    time_since_last_run = current_time - self.last_update_timestamp

                    if time_since_last_run > REFRESH_INTERVAL:
                        await self._regenerate_message()
                        self.last_update_timestamp = current_time

            buttons = [
                BetButton(
                    guild=self.guild,
                    config=self.config,
                    bet_config_id=self.bet_config_id,
                    style=discord.ButtonStyle.primary,
                    option_id=option['id'],
                    label=f"{option['option_name']}",
                    emoji=discord.PartialEmoji(name="💸"),
                    row=1,
                    callback=throttled_regenerate
                )
                for option in config['options']
            ]

            for button in buttons:
                if bet_total > 0:
                    if bet_totals[button.option_id] == 0:
                        button.label = f"{button.label}"
                    else:
                        button.label = f"{button.label} ({1 / (bet_totals[button.option_id] / bet_total):.1f}x)"
                    # else:
                    #     odds_ratio = bet_totals[button.option_id] / (bet_total - bet_totals[button.option_id])

                    #     if odds_ratio > 1:
                    #         button.label = f"{button.label} - {odds_ratio:.1f} : 1"
                    #     else:
                    #         button.label = f"{button.label} - 1 : {1/odds_ratio:.1f}"

                if config['state'] != 'open':
                    button.disabled = True

                button.custom_id = f"bet:{self.bet_config_id}:{button.option_id}"

                self.add_item(button)

            self.add_item(self.check_bet)
            self.add_item(self.list_winners)

        return self

    async def _author_check(self, interaction: discord.Interaction):
        config = await self._get_config()

        if interaction.user.id != config['author_id']:
            await interaction.response.send_message("❌ ERROR: You are not the author of this bet.", ephemeral=True, delete_after=5)
            return False
        
        return True
    
    async def _author_or_mods_check(self, interaction: discord.Interaction):
        return (isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_roles) or await self._author_check(interaction)
    
    async def _regenerate_message(self):
        await self.generate()
        await self.original_message.edit(embed=await BetEmbed(
            config=self.config,
            ctx=self.ctx, 
            bet_config_id=self.bet_config_id
        ).generate(), view=self)

    @discord.ui.button(custom_id=f"edit_config:", label="Config", style=discord.ButtonStyle.secondary, row=0)
    async def edit_config(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.custom_id != self.edit_config.custom_id:
            return

        if not await self._author_check(interaction):
            return
        
        config = await self._get_config()

        modal = BetAdministrationConfigModal(bet_config=config, started=config['state'] != 'config')

        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        if modal.is_data_changed:
            config = modal.bet_config
            await self._set_config(
                description=config['description'], 
                title=config['title'], 
                minimum_bet=config['minimum_bet'], 
                options=config['options'],
            )

            self.is_configed = True

            await self._regenerate_message()
        
        pass

    @discord.ui.button(label="Open", style=discord.ButtonStyle.primary, emoji=discord.PartialEmoji(name="🎰"), row=0)
    async def toggle_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.custom_id != self.toggle_open.custom_id:
            return

        if not await self._author_check(interaction):
            return 
        
        config = await self._get_config()
        
        if config['state'] == 'resolved' or config['state'] == 'cancelled':
            await interaction.response.send_message("❌ ERROR: Bet is already resolved or cancelled.", ephemeral=True, delete_after=5)
            return
        
        config['state'] = 'open' if config['state'] == 'closed' or config['state'] == 'config' else 'closed'
        await self._set_config(state=config['state'])

        await self._regenerate_message()

        await interaction.response.send_message(f"Betting is now {config['state']}.", ephemeral=True, delete_after=5)
        
        pass

    @discord.ui.button(label="Add Pool", style=discord.ButtonStyle.secondary, row=0)
    async def add_pool(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.custom_id != self.add_pool.custom_id:
            return
        
        if not await self._author_or_mods_check(interaction):
            return
        
        # Spawn a modal.
        modal = NumberPromptModal(
            custom_id="pool_amount",
            title="Add To Pool",
            author=interaction.user,
            max=100000000,
            min=-100000000,
            placeholder="Enter the amount to add to the pool.",
            label="Pool Amount",
        )
        await interaction.response.send_modal(modal)
        if await modal.wait():
            return

        amount = int(modal.item.value)
            
        if amount == 0:
            return
            
        async with self.config.guild(self.guild).active_bets.get_lock():
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            config = active_bets[str(self.bet_config_id)]

            config['base_value'] += amount

            if config['base_value'] < 0:
                amount -= config['base_value']
                config['base_value'] = 0

            active_bets.update({str(self.bet_config_id): config})
            await self.config.guild(self.guild).active_bets.set(active_bets)

        total = sum(better['bet_amount'] for better in config['betters']) + config['base_value']

        if amount > 0:
            msg = f"💰 `+{amount}` has been added to the pool. New total: `{total}` (Base: `{config['base_value']}`)"
        else:
            msg = f"💸 `{amount}` has been removed from the pool. New total: `{total}` (Base: `{config['base_value']}`)"

        await interaction.followup.send(msg, ephemeral=True)

        await self._regenerate_message()

        pass

    @discord.ui.button(label="Resolve", style=discord.ButtonStyle.success, row=0)
    async def resolve(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.custom_id != self.resolve.custom_id:
            return
        
        if not await self._author_check(interaction):
            return
        
        config = await self._get_config()

        action_bar = ChooseWinnerView(bet_config=config)

        await interaction.response.send_message("Select the winning option:", ephemeral=True, view=action_bar)

        if await action_bar.wait():
            return
        
        await interaction.delete_original_response()
        
        config['state'] = 'resolved'
        await self._set_config(state=config['state'])

        async with self.config.guild(self.guild).active_bets.get_lock():
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            config = active_bets[str(self.bet_config_id)]
            config['winning_option_id'] = action_bar.select_winner.bet_config['winning_option_id']

            bet_totals = {option['id']: 0 for option in config['options']}
            for better in config['betters']:
                bet_totals[better['bet_option_id']] += better['bet_amount']

            bet_total = sum(bet_totals.values())

            if bet_total == 0:
                await interaction.followup.send("No bets were placed.", ephemeral=True)
                return

            winning_option = next((option for option in config['options'] if option['id'] == config['winning_option_id']), None)

            pool_total = bet_total + config['base_value']

            if winning_option is None:
                raise ValueError(f"Winning option `{config['winning_option_id']}` not found.")

            await interaction.followup.send(f"🎉 The winning option is `{winning_option['option_name']}`. Total pool: `{pool_total}`", ephemeral=True)

            results_msg = ""

            for better in config['betters']:
                member = self.guild.get_member(better['member_id']) or await self.ctx.bot.fetch_user(better['member_id'])
                if better['bet_option_id'] == winning_option['id']:
                    share = better['bet_amount'] / bet_totals[winning_option['id']]
                    total_winnings = int(pool_total * share)
                    new_balance = await Coins._add_balance(member, total_winnings) # type: ignore[arg-type]
                    # results_msg += f"💸 {member.mention} won `{total_winnings}` " + \
                    #                   f"(+{total_winnings/better['bet_amount'] - 1:.2%}) " if total_winnings != better['bet_amount'] else '' + \
                    #                   f"from the bet `{config['title']}`. New Balance: `{new_balance}`" # type: ignore[arg-type]
                else:
                    # await member.send(f"🧾 `{config['title']}` has resolved. ")
                    pass

            active_bets.update({str(self.bet_config_id): config})
            await self.config.guild(self.guild).active_bets.set(active_bets)    

        await self._regenerate_message()    
        pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.custom_id != self.cancel.custom_id:
            return
        
        if not await self._author_check(interaction):
            return
        
        config = await self._get_config()
        config['state'] = 'cancelled'
        await self._set_config(state=config['state'])

        await self._regenerate_message()

        await interaction.response.send_message(f"Bets have been cancelled.", ephemeral=True, delete_after=5)

        async with self.config.guild(self.guild).active_bets.get_lock():
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            config = active_bets[str(self.bet_config_id)]

            for better in config['betters']:
                member = self.guild.get_member(better['member_id']) or await self.ctx.bot.fetch_user(better['member_id'])
                await Coins._add_balance(member, better['bet_amount']) # type: ignore[arg-type]
                # await member.send(f"💸 Your bet of `{better['bet_amount']}` has been refunded for the cancelled bet `{config['title']}`") # type: ignore[arg-type]        
        pass

    @discord.ui.button(label="Check Bet", style=discord.ButtonStyle.secondary, row=2)
    async def check_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if button.custom_id != self.check_bet.custom_id:
            return
        
        config = await self._get_config()
        better = next((better for better in config['betters'] if better['member_id'] == interaction.user.id), None)

        bet_totals = {option['id']: 0 for option in config['options']}
        for b in config['betters']:
            bet_totals[b['bet_option_id']] += b['bet_amount']

        bet_total = sum(bet_totals.values())
        
        pool_total = bet_total + config['base_value']

        if better:
            bet_option = next((option for option in config['options'] if option['id'] == better['bet_option_id']), None)
            if bet_option is None:
                raise ValueError(f"Option `{better['bet_option_id']}` not found.")
            
            results_msg : str

            if config['state'] == 'resolved':
                if better['bet_option_id'] == config['winning_option_id']:
                    share = better['bet_amount'] / bet_totals[config['winning_option_id']] # type: ignore[index]
                    total_winnings = int(pool_total * share)

                    balance = await Coins._get_balance(interaction.user) # type: ignore[arg-type]

                    results_msg = f"💸 You bet `{better['bet_amount']}` and won `{total_winnings}` " + \
                    (f"(+{total_winnings/better['bet_amount'] - 1:.2%}) " if total_winnings > better['bet_amount'] else '') + \
                    f"from the bet `{config['title']}`.\nCurrent Balance: `{balance}`" # type: ignore[arg-type]
                else:
                    results_msg = f"You lost {better['bet_amount']} betting on `{bet_option['option_name']}` in `{config['title']}`" # type: ignore[arg-type]
            else:
                results_msg = f"You are currently betting `{better['bet_amount']}` on `{bet_option['option_name']}`"
            
            await interaction.response.send_message(results_msg, ephemeral=True) 
        else:
            await interaction.response.send_message("You have not placed a bet on this pool.", ephemeral=True, delete_after=5)

    @discord.ui.button(label="Check Winners", style=discord.ButtonStyle.secondary, row=2)
    async def list_winners(self, interaction: discord.Interaction, button: discord.ui.Button):       
        if button.custom_id != self.list_winners.custom_id:
            return
        
        if not await self._author_or_mods_check(interaction):
            return
        
        config = await self._get_config()

        if config['winning_option_id'] is None:
            await interaction.response.send_message("Winning option has not been selected.", ephemeral=True, delete_after=5)
            return
        
        bet_totals = {option['id']: 0 for option in config['options']}
        for better in config['betters']:
            bet_totals[better['bet_option_id']] += better['bet_amount']

        bet_total = sum(bet_totals.values())
        
        pool_total = bet_total + config['base_value']
        remainder = pool_total

        betters_list = sorted(config['betters'], key=lambda x: (x['bet_option_id'] == config['winning_option_id'], x['bet_amount']), reverse=True)

        csv = "Member ID, Member, Bet Amount, Winning Amount\n"

        results_msg = f"Bet Pool: `{config['title']}` (`{config['id']}`)\n"
        results_msg += f"Winning Option: `{config['options'][config['winning_option_id']]['option_name']}`\n"
        results_msg += f"Total Payout: `{pool_total}`\n\n"
        for i, better in enumerate(betters_list):
            member = self.guild.get_member(better['member_id'])
            if better['bet_option_id'] == config['winning_option_id']:
                results_msg += "💸 "
                share = better['bet_amount'] / bet_totals[config['winning_option_id']] # type: ignore[index]
                total_winnings = int(pool_total * share)
            else:
                total_winnings = 0

            if i < MAX_WINNERS_DISPLAY_LENGTH:
                results_msg += (member.mention if member else f"`{better['member_id']}`") + f" bet `{better['bet_amount']}`"
                results_msg += f" on `{config['options'][better['bet_option_id']]['option_name']}`"
                results_msg += f" and won `{total_winnings}` " + \
                    f"(+{total_winnings/better['bet_amount'] - 1:.2%}) " if total_winnings > better['bet_amount'] else ''
                
                results_msg += "\n"
            
            if len(betters_list) > MAX_WINNERS_DISPLAY_LENGTH:
                csv += f"{better['member_id']}, {member}, {better['bet_amount']}, {total_winnings}\n"

        if len(betters_list) > MAX_WINNERS_DISPLAY_LENGTH:
            results_msg += f"\n`{len(betters_list) - MAX_WINNERS_DISPLAY_LENGTH}` remaining winners earned `{remainder}`"

            await interaction.user.send(content="Winners List", file=discord.File(fp=io.StringIO(csv), filename=f"{config['id']}_winners.csv")) # type: ignore[arg-type]

        await interaction.response.send_message(results_msg)
        
        
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: Item) -> None: # type: ignore[override]
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ ERROR: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ ERROR: {error}", ephemeral=True, delete_after=15)

    async def on_timeout(self) -> None:
        await self.original_message.edit(view=None)