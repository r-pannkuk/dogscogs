import typing
import discord
from redbot.core.config import Config

from dogscogs.views.paginated import OnCallbackSelect
from dogscogs.views.prompts import NumberPromptModal

from ..embed import get_modifier_strings              # type: ignore[import-untyped]
from ..config import BonusType, Modifier, OperatorType, KeyType   # type: ignore[import-untyped]


class EditModifierView(discord.ui.View):
    config : Config
    guild : discord.Guild
    author_id : int
    modifier : Modifier
    interaction : discord.Interaction

    key_input : discord.ui.Select
    operator_input : discord.ui.Select
    bonus_type_input : discord.ui.Select

    is_confirmed: bool = False

    def __init__(
        self,
        *args,
        config: Config,
        interaction: discord.Interaction,
        modifier: Modifier,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.config = config
        self.guild = interaction.guild         # type: ignore[assignment]
        self.author_id = interaction.user.id
        self.modifier = modifier
        self.interaction = interaction

    async def send(self) -> "EditModifierView":
        self.clear_items()

        pretty_labels = {
            'rolecolors': 'Color Curses',
            'nyame': 'Nyame Curses',
            'curse': 'Nickname Curses',

            'set': 'Set (Lock to a value)',
            'add': 'Add',
            'multiply': 'Multiply (Dice Roll Only)',

            'attack': 'Attack Rolls',
            'defend': 'Defense Rolls',
            'both': 'Attack & Defense Rolls',
        }

        async def set_operator(values): 
            self.modifier['operator'] = values[0]
            await self.send()

        self.operator_input = OnCallbackSelect(
            placeholder="Select a modifier operator.",
            options=[
                discord.SelectOption(
                    label=pretty_labels[operator],
                    value=operator,
                    default=True if operator == self.modifier['operator'] else False,
                )
                for operator in typing.get_args(OperatorType)
            ],
            max_values=1,
            row=1,
            callback=set_operator
        )

        async def set_key(values): 
            self.modifier['key'] = values[0]
            await self.send()

        self.key_input = OnCallbackSelect(
            placeholder="Select a modifier key.",
            options=[
                discord.SelectOption(
                    label=pretty_labels[key],
                    value=key,
                    default=True if key == self.modifier['key'] else False,
                )
                for key in typing.get_args(KeyType)
            ]
            ,
            max_values=1,
            row=0,
            callback=set_key
        )

        async def set_bonus_type(values): 
            self.modifier['type'] = values[0]
            await self.send()

        self.bonus_type_input = OnCallbackSelect(
            placeholder="Select a bonus type.",
            options=[
                discord.SelectOption(
                    label=pretty_labels[bonus_type],
                    value=bonus_type,
                    default=True if bonus_type == self.modifier['type'] else False,
                )
                for bonus_type in typing.get_args(BonusType)
            ],
            max_values=1,
            row=2,
            callback=set_bonus_type
        )

        self.add_item(self.key_input)
        self.add_item(self.operator_input)
        self.add_item(self.bonus_type_input)

        self.add_item(self.edit_value)
        self.add_item(self.save)
        self.add_item(self.cancel)

        msg_string = "Setting Modifier:\n"
        msg_string += f"`{get_modifier_strings([self.modifier])[0]}`"

        if self.interaction.response.is_done():
            await self.interaction.edit_original_response(content=msg_string, view=self) # type: ignore[union-attr]
        else:
            await self.interaction.response.send_message(content=msg_string, ephemeral=True, view=self)

        return self

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            raise Exception("You are not the author of this view.")

        return True
    
    @discord.ui.button(label="Edit Value", style=discord.ButtonStyle.secondary, row=3)
    async def edit_value(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = NumberPromptModal(
            placeholder="Enter a value for the modifier.",
            label="Amount",
            author=self.guild.get_member(self.author_id),    # type: ignore[arg-type]
            title="Modifier Value",
            default=self.modifier['value'],
            min=-999999,
            max=999999,
            custom_id="modifier_value",
            use_float=True,
            row=3,
        )

        await interaction.response.send_modal(modal)
        if await modal.wait():
            return
        
        self.modifier['value'] = float(modal.item.value)

        if int(self.modifier['value']) == self.modifier['value']:
            self.modifier['value'] = int(self.modifier['value'])

        await self.send()
        
        pass
    
    @discord.ui.button(label="Save", style=discord.ButtonStyle.green, row=4)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        self.is_confirmed = True

        await self.interaction.delete_original_response()

        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, row=4)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        self.is_confirmed = False

        await self.interaction.delete_original_response()

        self.stop()
