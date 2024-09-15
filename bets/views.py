import typing
import discord
from discord.ui.item import Item
from redbot.core import commands
from redbot.core.config import Config

from dogscogs.views.prompts import NumberPromptTextInput, NumberPromptModal
from dogscogs.views.confirmation import ConfirmationView

from coins import Coins

from .bets import DEFAULT_BET_DESCRIPTION, DEFAULT_BET_TITLE
from .config import BetConfig, BetOption, BetState, Better
from .embed import BetEmbed

# class BetAdministrationButton(discord.ui.Button):
#     def __init__(
#             self, 
#             *args,
#             config: Config,
#             author: discord.Member, 
#             bet_config_id: BetConfig, 
#             **kwargs
#         ):
#         super().__init__(*args, **kwargs)
#         self.author = author
#         self.bet_config = bet_config


#     async def callback(self, interaction: discord.Interaction) -> None:
#         pass

#     async def interaction_check(self, interaction: discord.Interaction) -> bool:
#         return True

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
        await interaction.response.send_message("Are you sure?", ephemeral=True, view=confirmation_view)

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
            await interaction.response.send_message("❌ ERROR: You are not the author of this bet.", ephemeral=True, delete_after=15)
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
            await interaction.response.send_message("You must have at least 2 options.", ephemeral=True, delete_after=15)
            return False
        
        distinct_options = set(parsed_options)

        if len(distinct_options) != len(parsed_options):
            await interaction.response.send_message("❌ ERROR: Options must be distinct.", ephemeral=True, delete_after=15)
            return False
        
        return True
    
    async def on_submit(self, interaction: discord.Interaction) -> None:
        self.bet_config['title'] = self.bet_title.value.strip().strip("\"\'")
        self.bet_config['description'] = self.bet_description.value.strip().strip("\"\'")
        
        if self.bet_minimum.value.isnumeric():
            self.bet_config['minimum_bet'] = int(self.bet_minimum.value)

        self.bet_config['options'] = [{"id": i, "option_name": option} for i, option in enumerate(self._get_options())]

        await interaction.response.send_message("Bet configuration updated.", ephemeral=True, delete_after=15)
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

            active_bets.update({str(self.bet_config_id): config})
            
            await self.config.guild(self.guild).active_bets.set(active_bets)
    
    async def generate(self) -> "BetAdministrationView":
        config = await self._get_config()

        if not self.is_configed:
            self.is_configed = config['state'] != 'config'

        self.clear_items()

        self.add_item(self.edit_config)

        if self.is_configed:
            if config['state'] == 'config':
                self.edit_config.disabled = False

                self.toggle_open.disabled = False
                self.toggle_open.label = "Open"
                self.toggle_open.emoji = discord.PartialEmoji(name="🎰")

                self.resolve.disabled = True

                self.cancel.disabled = False

                self.add_pool.disabled = False

                self.check_bet.disabled = True
            if config['state'] == 'open':
                self.edit_config.disabled = False
                
                self.toggle_open.disabled = False
                self.toggle_open.label = "Close"
                self.toggle_open.emoji = discord.PartialEmoji(name="🔒")
                
                self.resolve.disabled = True

                self.cancel.disabled = False

                self.check_bet.disabled = False
            elif config['state'] == 'closed':
                self.edit_config.disabled = False

                self.toggle_open.disabled = False
                self.toggle_open.label = "Open"
                self.toggle_open.emoji = discord.PartialEmoji(name="🎰")
                
                self.resolve.disabled = False

                self.cancel.disabled = False

                self.check_bet.disabled = False
            elif config['state'] == 'cancelled':
                self.edit_config.disabled = True
                
                self.toggle_open.disabled = True
                
                self.resolve.disabled = True

                self.cancel.disabled = True

                self.add_pool.disabled = True

                self.check_bet.disabled = True
            elif config['state'] == 'resolved':
                self.edit_config.disabled = True
                
                self.toggle_open.disabled = True
                
                self.resolve.disabled = True

                self.cancel.disabled = True

                self.add_pool.disabled = True

                self.check_bet.disabled = True

            self.add_item(self.toggle_open)
            self.add_item(self.resolve)
            self.add_item(self.cancel)
            self.add_item(self.add_pool)

            bet_totals = {option['id']: 0 for option in config['options']}
            for better in config['betters']:
                bet_totals[better['bet_option_id']] += better['bet_amount']

            bet_total = sum(bet_totals.values())

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
                    callback=self._regenerate_message
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

                self.add_item(button)

            self.add_item(self.check_bet)

        return self

    async def _author_check(self, interaction: discord.Interaction):
        config = await self._get_config()

        if interaction.user.id != config['author_id']:
            await interaction.response.send_message("❌ ERROR: You are not the author of this bet.", ephemeral=True, delete_after=15)
            return False
        
        return True
    
    async def _author_or_mods_check(self, interaction: discord.Interaction):
        return await self._author_check(interaction) or \
            isinstance(interaction.user, discord.Member) and interaction.user.guild_permissions.manage_roles
    
    async def _regenerate_message(self):
        await self.generate()
        await self.original_message.edit(embed=await BetEmbed(
            config=self.config,
            ctx=self.ctx, 
            bet_config_id=self.bet_config_id
        ).generate(), view=self)

    @discord.ui.button(label="Config", style=discord.ButtonStyle.secondary, row=0)
    async def edit_config(self, interaction: discord.Interaction, button: discord.ui.Button):
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

    @discord.ui.button(label="Toggle Open", style=discord.ButtonStyle.primary, row=0)
    async def toggle_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._author_check(interaction):
            return 
        
        config = await self._get_config()
        
        if config['state'] == 'resolved' or config['state'] == 'cancelled':
            await interaction.response.send_message("❌ ERROR: Bet is already resolved or cancelled.", ephemeral=True, delete_after=15)
            return
        
        config['state'] = 'open' if config['state'] == 'closed' or config['state'] == 'config' else 'closed'
        await self._set_config(state=config['state'])

        await self._regenerate_message()

        await interaction.response.send_message(f"Betting is now {config['state']}.", ephemeral=True, delete_after=15)
        
        pass

    @discord.ui.button(label="Add Pool", style=discord.ButtonStyle.secondary, row=0)
    async def add_pool(self, interaction: discord.Interaction, button: discord.ui.Button):
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

        await self._regenerate_message()

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

            for better in config['betters']:
                member = self.guild.get_member(better['member_id']) or await self.ctx.bot.fetch_user(better['member_id'])
                if better['bet_option_id'] == winning_option['id']:
                    share = better['bet_amount'] / bet_totals[winning_option['id']]
                    total_winnings = int(pool_total * share)
                    new_balance = await Coins._add_balance(member, total_winnings) # type: ignore[arg-type]
                    await member.send(f"💸 You have won `{total_winnings}` " + \
                                      f'(+{total_winnings/better['bet_amount'] - 1:.2%}%) ' if total_winnings != better['bet_amount'] else '' + \
                                      f"from the bet `{config['title']}`. New Balance: `{new_balance}`") # type: ignore[arg-type]
                # else:
                #     await member.send(f"💸 You have lost `{better['bet_amount']}` from the bet `{config['title']}`")

            active_bets.update({str(self.bet_config_id): config})
            await self.config.guild(self.guild).active_bets.set(active_bets)

        self.stop()
        
        pass

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=0)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._author_check(interaction):
            return
        
        config = await self._get_config()
        config['state'] = 'cancelled'
        await self._set_config(state=config['state'])

        await self._regenerate_message()

        await interaction.response.send_message(f"Bets have been cancelled.", ephemeral=True, delete_after=15)

        async with self.config.guild(self.guild).active_bets.get_lock():
            active_bets : typing.Dict[str, BetConfig] = await self.config.guild(self.guild).active_bets()
            config = active_bets[str(self.bet_config_id)]

            for better in config['betters']:
                member = self.guild.get_member(better['member_id']) or await self.ctx.bot.fetch_user(better['member_id'])
                await Coins._add_balance(member, better['bet_amount']) # type: ignore[arg-type]
                await member.send(f"💸 Your bet of `{better['bet_amount']}` has been refunded for the cancelled bet `{config['title']}`") # type: ignore[arg-type]


        self.stop()
        
        pass

    @discord.ui.button(label="Check Bet", style=discord.ButtonStyle.secondary, row=2)
    async def check_bet(self, interaction: discord.Interaction, button: discord.ui.Button):
        config = await self._get_config()
        better = next((better for better in config['betters'] if better['member_id'] == interaction.user.id), None)

        if better:
            bet_option = next((option for option in config['options'] if option['id'] == better['bet_option_id']), None)
            if bet_option is None:
                raise ValueError(f"Option `{better['bet_option_id']}` not found.")
            
            await interaction.response.send_message(f"You are currently betting `{better['bet_amount']}` on `{bet_option['option_name']}`", ephemeral=True) 
        else:
            await interaction.response.send_message("You have not placed a bet on this pool.", ephemeral=True, delete_after=15)
        
        
    async def on_error(self, interaction: discord.Interaction, error: Exception, item: Item) -> None: # type: ignore[override]
        if interaction.response.is_done():
            await interaction.followup.send(f"❌ ERROR: {error}", ephemeral=True)
        else:
            await interaction.response.send_message(f"❌ ERROR: {error}", ephemeral=True, delete_after=15)