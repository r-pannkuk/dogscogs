import typing
import uuid
import discord
from redbot.core.config import Config

from dogscogs.views.paginated import PaginatedEmbed, OnCallbackSelect
from dogscogs.views.prompts import ValidImageURLTextInput, NumberPromptTextInput
from dogscogs.views.confirmation import ConfirmationView
from dogscogs.constants.discord.views import MAX_SELECT_OPTIONS as DISCORD_MAX_SELECT_OPTIONS

from coins import Coins

from .utils import EditModifierView
from ..embed import BattlerEquipmentEmbed, get_modifier_strings
from ..config import BattleUserConfig, BonusType, Modifier, OperatorType, Equipment, KeyType, SlotType

DEFAULT_NAME = "<NAME>"
DEFAULT_DESCRIPTION = "<DESCRIPTION>"
DEFAULT_IMAGE_URL = "https://wiki.koumakan.jp/images/hisouten/e/ed/Soku_common_card000.png"

class EditEquipmentDetailsModal(discord.ui.Modal):
    name_input : discord.ui.TextInput
    description_input: discord.ui.TextInput
    cost_input: NumberPromptTextInput
    image_url_input: ValidImageURLTextInput
    
    def __init__(
        self,
        *args,
        config: Config,
        guild: discord.Guild,
        equipment_id: int,
        author_id: int,
        **kwargs,
    ):
        super().__init__(*args, title="Edit Equipment Details", **kwargs)

        self.config = config
        self.guild = guild
        self.equipment_id = equipment_id
        self.author_id = author_id

    async def _get_config(self) -> Equipment:
        equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        found_equipment = next((e for e in equipment if e['id'] == self.equipment_id), None)

        if found_equipment is None:
            raise ValueError(f"Equipment with ID {self.equipment_id} not found in {self.guild.name}.")
        
        return found_equipment
    
    async def _set_config(
        self,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        cost: typing.Optional[int] = None,
        image_url: typing.Optional[str] = None,
    ) -> None:
        async with self.config.guild(self.guild).equipment.get_lock():
            equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
            found_equipment = next((e for e in equipment if e['id'] == self.equipment_id), None)

            if found_equipment is None:
                raise ValueError(f"Equipment with ID {self.equipment_id} not found in {self.guild.name}.")
            
            if name is not None:
                found_equipment['name'] = name
            if description is not None:
                found_equipment['description'] = description
            if cost is not None:
                found_equipment['cost'] = cost
            if image_url is not None:
                found_equipment['image_url'] = image_url

            equipment = [e for e in equipment if e['id'] != self.equipment_id]
            equipment.append(found_equipment)
            equipment.sort(key=lambda e: e['name'])

            await self.config.guild(self.guild).equipment.set(equipment)

    async def collect(self) -> "EditEquipmentDetailsModal":
        equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        found_equipment = next((e for e in equipment if e['id'] == self.equipment_id), None)

        if found_equipment is None:
            raise ValueError(f"Equipment with ID {self.equipment_id} not found in {self.guild.name}.")
        
        self.clear_items()

        self.name_input = discord.ui.TextInput(
            placeholder="Enter the name of the equipment",
            required=True,
            default=found_equipment['name'],
            label="Equipment Name",
            max_length=100,
            style=discord.TextStyle.short,
        )
        self.description_input = discord.ui.TextInput(
            placeholder="Enter a description of the equipment",
            required=True,
            default=found_equipment['description'],
            label="Equipment Description",
            style=discord.TextStyle.long,
        )
        self.cost_input = NumberPromptTextInput(
            placeholder="Enter the cost of the equipment",
            required=True,
            default=str(found_equipment['cost']) if found_equipment['cost'] is not None else None,
            label="Equipment Cost",
            min=0,
            max=9999999,
            style=discord.TextStyle.short,
        )
        self.image_url_input = ValidImageURLTextInput(
            placeholder="Provide an image link (.png, .jog, .jpeg, or .gif)",
            required=True,
            default=found_equipment['image_url'],
            label="Equipment Image",
            style=discord.TextStyle.long,
        )

        self.add_item(self.name_input)
        self.add_item(self.description_input)
        self.add_item(self.cost_input)
        self.add_item(self.image_url_input)

        return self
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You are not the author of this view.", ephemeral=True, delete_after=10)
            return False
        
        return (
            await self.cost_input.interaction_check(interaction) 
            # and 
            # await self.image_url_input.interaction_check(interaction)
        )
    
    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value
        description = self.description_input.value
        cost = int(float(self.cost_input.value))
        image_url = self.image_url_input.value

        await self._set_config(
            name=name,
            description=description,
            cost=cost,
            image_url=image_url,
        )

        await interaction.response.send_message("Saved changes.", ephemeral=True, delete_after=5)
        self.stop()

class _EquipmentPaginatedEmbed(PaginatedEmbed):
    config : Config
    guild: discord.Guild
    slot_types : typing.List[SlotType] = []
    
    select_slot : typing.Optional[OnCallbackSelect] = None
    select_list : typing.Optional[OnCallbackSelect] = None

    def __init__(
        self,
        *args,
        config : Config,
        interaction : typing.Optional[discord.Interaction] = None,
        original_message: typing.Optional[discord.Message] = None,
        show_stats : bool = False,
        **kwargs,
    ):
        if interaction is None and original_message is None:
            raise ValueError("Either interaction or original_message must be provided.")
        
        async def get_page(index : int) -> typing.Tuple[discord.Embed, int]:
            guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()

            if not guild_equipment or len(guild_equipment) == 0:
                return discord.Embed(
                    title="No Equipment", 
                    description=f"There isn't any equipment found in {self.guild.name}.",
                    color=discord.Color.red()
                ), 1
            
            filtered_equipment = [e for e in guild_equipment if len(self.slot_types) == 0 or e['slot'] in self.slot_types]

            if len(filtered_equipment) == 0:
                return discord.Embed(
                    title="No Equipment", 
                    description=f"There isn't any equipment found in {self.guild.name} for slot(s) {', '.join([f'`{t.capitalize()}`' for t in self.slot_types])}.", 
                    color=discord.Color.red()
                ), 1
            
            return await BattlerEquipmentEmbed(
                config = self.config,
                guild = self.guild,
                equipment_id = filtered_equipment[index]["id"]
            ).send(show_stats=show_stats), len(filtered_equipment)

        super().__init__(
            *args, 
            interaction=interaction, 
            message=original_message, 
            get_page=get_page, 
            **kwargs
        )

        self.config = config
        self.guild = self.interaction.guild if self.interaction else self.original_message.guild # type: ignore[assignment,union-attr]

    async def edit_page(self) -> None:
        _, size = await self.get_page(0)

        if size > 1 and size < DISCORD_MAX_SELECT_OPTIONS:
            guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
            filtered_equipment = [e for e in guild_equipment if len(self.slot_types) == 0 or e['slot'] in self.slot_types]

            async def edit_selected_page(values: typing.List[str]) -> None:
                self.index = int(values[0])
                await self.edit_page()

            options = [
                discord.SelectOption(
                    label=e['name'],
                    value=str(i),
                    default=True if i == self.index else False
                )
                for i, e in enumerate(filtered_equipment)
            ]

            if self.select_list is None:
                self.select_list : OnCallbackSelect = OnCallbackSelect(
                    custom_id="equipment_list",
                    placeholder="Select an equipment",
                    options=options,
                    callback=edit_selected_page,
                    row=2,
                    max_values=1,
                    min_values=1,
                )
                self.add_item(self.select_list)
            else:
                self.select_list.options = options

        elif size <= 1:
            if self.select_list is not None:
                self.remove_item(self.select_list)
                self.select_list = None
            # self.previous.disabled = True
            # self.next.disabled = True

        if any((c.custom_id == "equipment_slot" for c in self.children)) and self.select_slot is not None: # type: ignore[attr-defined]
            self.remove_item(self.select_slot)

        async def set_slot(values): 
            self.slot_types = values
            await self.edit_page()

        self.select_slot : OnCallbackSelect = OnCallbackSelect(
            custom_id="equipment_slot",
            placeholder="Filter by slot",
            callback=set_slot,
            options=[
                discord.SelectOption(
                    default=slot in self.slot_types,
                    label=slot.capitalize(),
                    value=slot,
                )
                for slot in typing.get_args(SlotType)
            ],
            max_values=len(typing.get_args(SlotType)),
            min_values=0,
            row=1,
        )

        self.add_item(self.select_slot)

        await super().edit_page()
    
    async def send(self) -> "_EquipmentPaginatedEmbed":
        await super().send()

        self.update_buttons()
        await self.edit_page()
        await self.message.edit(view=self)

        return self
    
class AdminEquipmentConfigure(discord.ui.View):
    slot_select_input : OnCallbackSelect
    select_modifier : typing.Union[discord.ui.Select, None] = None
    index : int = -1

    def __init__(
        self,
        config: Config,
        guild: discord.Guild,
        message: discord.Message,
        author_id : int,
        equipment_id : int,
    ):
        super().__init__()

        self.config = config
        self.guild = guild
        self.message = message
        self.author_id = author_id
        self.equipment_id = equipment_id

    async def _get_config(self) -> Equipment:
        guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        found_equipment = next((e for e in guild_equipment if e['id'] == self.equipment_id), None)

        if found_equipment is None:
            raise ValueError(f"Equipment with ID {self.equipment_id} not found in {self.guild.name}.")
        
        return found_equipment
    
    async def _set_config(
        self,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        image_url: typing.Optional[str] = None,
        cost: typing.Optional[int] = None,
        slot : typing.Optional[SlotType] = None,
        modifiers: typing.Optional[typing.List[Modifier]] = None,
    ) -> None:
        async with self.config.guild(self.guild).races.get_lock():
            equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
            found_equipment = next((e for e in equipment if e['id'] == self.equipment_id), None)

            if found_equipment is None:
                raise ValueError(f"Equipment with ID {self.equipment_id} not found in {self.guild.name}.")
            
            if name is not None:
                found_equipment['name'] = name
            if description is not None:
                found_equipment['description'] = description
            if image_url is not None:
                found_equipment['image_url'] = image_url
            if cost is not None:
                found_equipment['cost'] = cost
            if slot is not None:
                found_equipment['slot'] = slot
            if modifiers is not None:
                found_equipment['modifiers'] = modifiers

            equipment = [e for e in equipment if e['id'] != self.equipment_id]
            equipment.append(found_equipment)
            equipment.sort(key=lambda e: e['name'])

            await self.config.guild(self.guild).equipment.set(equipment)

    async def collect(self) -> "AdminEquipmentConfigure":
        equipment = await self._get_config()

        self.clear_items()

        self.add_item(self.edit_details)

        async def set_slot(values):
            slot = values[0]
            await self._set_config(slot=slot)
            await self.collect()

        self.slot_select_input : OnCallbackSelect = OnCallbackSelect(
            max_values=1,
            placeholder="Select a slot for this equipment.",
            options=[
                discord.SelectOption(
                    label=slot.capitalize(),
                    value=slot,
                    default=True if equipment['slot'] == slot else False,
                )
                for slot in typing.get_args(SlotType)
            ],
            min_values=1,
            callback=set_slot,
            row=1,
        )

        self.add_item(self.slot_select_input)

        if len(equipment['modifiers']) == 1:
            self.index = 0
        elif len(equipment['modifiers']) > 1:

            async def return_none(values):
                self.index = int(values[0])
                await self.collect()
                return None
            
            self.select_modifier : OnCallbackSelect = OnCallbackSelect(
                max_values=1,
                placeholder="Select a modifier to edit or delete.",
                options=[
                    discord.SelectOption(
                        label=get_modifier_strings([m])[0],
                        value=str(i),
                        default=True if i == self.index else False,
                    )
                    for i, m in enumerate(equipment['modifiers'])
                ],
                callback=return_none,
            )

            self.add_item(self.select_modifier)

        self.add_item(self.add_modifier)

        if len(equipment['modifiers']) >= 1:
            self.edit_modifier.disabled = self.index == -1
            self.delete_modifier.disabled = self.index == -1

            self.add_item(self.edit_modifier)
            self.add_item(self.delete_modifier)

        self.add_item(self.save)

        await self.message.edit(embed=await BattlerEquipmentEmbed(
            config=self.config,
            guild=self.guild,
            equipment_id=self.equipment_id,
        ).send(), view=self)

        return self
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You are not the author of this message.", ephemeral=True, delete_after=10)
            return False
        
        return True
    
    @discord.ui.button(label="Edit Details", style=discord.ButtonStyle.primary, row=0)
    async def edit_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = await EditEquipmentDetailsModal(
            config=self.config,
            guild=self.guild,
            author_id=self.author_id,
            equipment_id=self.equipment_id,
        ).collect()

        await interaction.response.send_modal(modal)
        if await modal.wait():
            return
        
        await self.message.edit(embed=await BattlerEquipmentEmbed(
            config=self.config,
            guild=self.guild,
            equipment_id=self.equipment_id,
        ).send(), view=self)

    @discord.ui.button(label="Add Modifier", style=discord.ButtonStyle.green, row=3)
    async def add_modifier(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = await EditModifierView(
            config=self.config,
            interaction=interaction,
            modifier={
                'key': typing.get_args(KeyType)[0],
                'operator': typing.get_args(OperatorType)[0],
                'type': typing.get_args(BonusType)[0],
                'value': 0,
            }
        ).send()

        if await view.wait() or not view.is_confirmed:
            return
        
        config = await self._get_config()

        modifiers = config['modifiers']
        modifiers.append(view.modifier)

        await self._set_config(modifiers=modifiers)

        await self.collect()

        await self.message.edit(embed=await BattlerEquipmentEmbed(
            config=self.config,
            guild=self.guild,
            equipment_id=self.equipment_id,
        ).send(), view=self)

        pass

    @discord.ui.button(label="Edit Modifier", style=discord.ButtonStyle.secondary, row=3)
    async def edit_modifier(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index == -1:
            raise ValueError("Something went wrong. Index shouldn't be -1")
        
        config : Equipment = await self._get_config()

        modifiers = config['modifiers']
        modifier = modifiers[self.index]

        view = await EditModifierView(
            config=self.config,
            interaction=interaction,
            modifier=modifier
        ).send()

        if await view.wait() or not view.is_confirmed:
            return
        
        modifiers[self.index] = view.modifier

        await self._set_config(modifiers=modifiers)

        await self.collect()

        await self.message.edit(embed=await BattlerEquipmentEmbed(
            config=self.config,
            guild=self.guild,
            equipment_id=self.equipment_id,
        ).send(), view=self)

    @discord.ui.button(label="Delete Modifier", style=discord.ButtonStyle.danger, row=3)
    async def delete_modifier(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index == -1:
            raise ValueError("Something went wrong. Index shouldn't be -1")
        
        config : Equipment = await self._get_config()

        modifier = config['modifiers'].pop(self.index)

        await self._set_config(modifiers=config['modifiers'])

        await self.collect()

        await interaction.response.send_message(f"Deleted modifier: {get_modifier_strings([modifier])[0]}", ephemeral=True, delete_after=10)

        await self.message.edit(embed=await BattlerEquipmentEmbed(
            config=self.config,
            guild=self.guild,
            equipment_id=self.equipment_id,
        ).send(), view=self)

    @discord.ui.button(label="Done Editing", style=discord.ButtonStyle.primary, row=4)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

class AdminEquipmentPaginatedEmbed(_EquipmentPaginatedEmbed):
    def __init__(
        self,
        *args,
        config: Config,
        interaction: typing.Optional[discord.Interaction] = None,
        original_message : typing.Optional[discord.Message] = None,
        **kwargs,
    ):
        super().__init__(
            *args, 
            config=config, 
            interaction=interaction, 
            original_message=original_message, 
            show_stats=True,
            **kwargs
        )

    @discord.ui.button(label="Add New", style=discord.ButtonStyle.primary, row=4)
    async def add_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()

        new_equipment : Equipment = {
            'id': uuid.uuid4().int,
            'name': DEFAULT_NAME,
            'description': DEFAULT_DESCRIPTION,
            'image_url': DEFAULT_IMAGE_URL,
            'cost': 0,
            'slot': 'head',
            'modifiers': [],
        }

        equipment.append(new_equipment)

        await self.config.guild(self.guild).equipment.set(equipment)

        self.index = len(equipment) - 1

        await self.edit_page()

        await interaction.response.defer()

        view = await AdminEquipmentConfigure(
            config=self.config,
            guild=self.guild,
            message=self.message,
            equipment_id=new_equipment['id'],
            author_id=self.author.id,
        ).collect()

        await self.message.edit(view=view)
        await view.wait()

        await self.edit_page()

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, row=4)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        equipment = guild_equipment[self.index]

        await interaction.response.defer()

        view = await AdminEquipmentConfigure(
            config=self.config,
            guild=self.guild,
            message=self.message,
            equipment_id=equipment['id'],
            author_id=self.author.id,
        ).collect()

        await self.message.edit(view=view)
        await view.wait()

        await self.edit_page()

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, row=4)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        equipment = guild_equipment.pop(self.index)

        view = ConfirmationView(author=self.author) # type: ignore[arg-type]

        await interaction.response.send_message(
            content=f"Are you sure you want to delete {equipment['name']}?",
            view=view,
            ephemeral=True,
        )

        if await view.wait() or not view.value:
            await interaction.delete_original_response()
            return
        
        member_data : typing.Dict[int, BattleUserConfig] = await self.config.all_members(self.guild)
        filtered_member_ids = [
            id
            for id, data in member_data.items()
            if any(id == equipment['id'] for id in data['equipment_ids'])
        ]

        async with self.config.get_members_lock(self.guild):
            for id in filtered_member_ids:
                member_equipment = await self.config.member_from_ids(self.guild.id, id).equipment_ids()
                member_equipment = [id for id in member_equipment if id != equipment['id']]
                await self.config.member_from_ids(self.guild.id, id).equipment_ids.set(member_equipment)

        await self.config.guild(self.guild).equipment.set(guild_equipment)

        await interaction.delete_original_response()

        self.index = max(self.index - 1, 0)

        await self.edit_page()

        pass

class PurchaseEquipmentPaginatedEmbed(_EquipmentPaginatedEmbed):
    def __init__(
        self,
        *args,
        config: Config,
        interaction: typing.Optional[discord.Interaction] = None,
        original_message : typing.Optional[discord.Message] = None,
        **kwargs,
    ):
        super().__init__(
            *args, 
            config=config, 
            interaction=interaction, 
            original_message=original_message, 
            show_stats=False,
            **kwargs
        )

    @discord.ui.button(label="Purchase", style=discord.ButtonStyle.primary, row=4)
    async def purchase(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        sell_ratio : float = await self.config.guild(self.guild).sell_ratio()
        equipment = guild_equipment[self.index]

        member_equipment_ids : typing.List[int] = await self.config.member(interaction.user).equipment_ids() # type: ignore[arg-type]
        member_equipment = [e for e in guild_equipment if e['id'] in member_equipment_ids]
        member_slot_piece = next((e for e in member_equipment if e['slot'] == equipment['slot']), None)
        member_piece_sell_value = int(member_slot_piece['cost'] * sell_ratio if member_slot_piece is not None else 0)

        if equipment['id'] in member_equipment_ids:
            await interaction.response.send_message(f"You already own `{equipment['name']}`.", ephemeral=True, delete_after=10)
            return
        
        balance = await Coins._get_balance(interaction.user) # type: ignore[arg-type]

        msg_content = f"__Equipment__: {equipment['name']} (`{equipment['slot'].capitalize()}`)\n"
        msg_content += f"__Cost__: {equipment['cost']}\n"
        msg_content += f"__Balance__: {balance}\n\n"
            
        async def sell_item(i : discord.Interaction):
            revised_member_equipment = [id for id in member_equipment_ids if id != member_slot_piece['id']] # type: ignore[index]
            await Coins._add_balance(i.user, member_piece_sell_value) # type: ignore[arg-type]

            await self.config.member(i.user).equipment_ids.set(revised_member_equipment)  # type: ignore[arg-type]

            return True

        view = None

        if balance < equipment['cost']:
            msg_content += f"You do not have enough currency to purchase `{equipment['name']}`."

            if member_slot_piece is None or balance + member_piece_sell_value < equipment['cost']:
                await interaction.response.send_message(content=msg_content, ephemeral=True, delete_after=10)
                return
            
            msg_content += f" Sell your {member_slot_piece['name']} ({equipment['slot'].capitalize()}) for {member_piece_sell_value} to make up the difference?"
            
        elif member_slot_piece is not None:
            msg_content += f"You already own a `{equipment['slot'].capitalize()}` piece: **{member_slot_piece['name']}**. Sell it for {member_piece_sell_value} and continue purchasing?"
        
        if member_slot_piece is not None:
            view = ConfirmationView(
                author=interaction.user,   # type: ignore[arg-type]
                callback=sell_item,
            )
        else:
            view = ConfirmationView(
                author=interaction.user,   # type: ignore[arg-type]
            )

        await interaction.response.send_message(content=msg_content, view=view, ephemeral=True)
        if await view.wait() or not view.value:
            await interaction.delete_original_response()
            return

        await interaction.delete_original_response()

        new_balance = await Coins._remove_balance(interaction.user, equipment['cost']) # type: ignore[arg-type]

        # Re-fetching here to make sure it's updated after any potential selling
        member_equipment_ids = await self.config.member(interaction.user).equipment_ids() # type: ignore[arg-type]

        member_equipment_ids.append(equipment['id'])

        await self.config.member(interaction.user).equipment_ids.set(member_equipment_ids) # type: ignore[arg-type]

        response_string = ""

        if member_slot_piece is not None:
            response_string += f"Sold **{member_slot_piece['name']}** (`{member_slot_piece['slot']}`) for {member_piece_sell_value}.\n"  # type: ignore[index]

        response_string += f"Purchased **{equipment['name']}** (`{equipment['slot']}`) for {equipment['cost']}.\n"
        response_string += f"New Balance: `{new_balance}`"

        await interaction.followup.send(content=response_string, ephemeral=True)

        pass