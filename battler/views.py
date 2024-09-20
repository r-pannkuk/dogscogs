import typing
import uuid
import discord
from redbot.core.config import Config

from dogscogs.views.paginated import PaginatedEmbed, OnCallbackSelect
from dogscogs.views.prompts import ValidImageURLTextInput, NumberPromptModal
from dogscogs.views.confirmation import ConfirmationView
from dogscogs.constants.discord.views import MAX_SELECT_OPTIONS as DISCORD_MAX_SELECT_OPTIONS

from .embed import BattlerRaceEmbed, get_modifier_strings              # type: ignore[import-untyped]

from .config import BattleUserConfig, BonusType, Modifier, OperatorType, Race, KeyType   # type: ignore[import-untyped]

DEFAULT_NAME = "<NAME>"
DEFAULT_DESCRIPTION = "<DESCRIPTION>"
DEFAULT_IMAGE_URL = "https://en.touhouwiki.net/images/a/a6/Th06Windmill.png"

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

        async def set_key(values): 
            self.modifier['key'] = values[0]
            await self.send()


        self.key_input = OnCallbackSelect(
            placeholder="Select a modifier key.",
            options=[
                discord.SelectOption(
                    label=key,
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

        async def set_operator(values): 
            self.modifier['operator'] = values[0]
            await self.send()

        self.operator_input = OnCallbackSelect(
            placeholder="Select a modifier operator.",
            options=[
                discord.SelectOption(
                    label=operator,
                    value=operator,
                    default=True if operator == self.modifier['operator'] else False,
                )
                for operator in typing.get_args(OperatorType)
            ],
            max_values=1,
            row=1,
            callback=set_operator
        )

        async def set_bonus_type(values): 
            self.modifier['type'] = values[0]
            await self.send()

        self.bonus_type_input = OnCallbackSelect(
            placeholder="Select a bonus type.",
            options=[
                discord.SelectOption(
                    label=bonus_type,
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
            default=self.modifier['value'], # type: ignore[arg-type]
            min=-999999,
            max=999999,
            custom_id="modifier_value",
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

class EditRaceDetailsModal(discord.ui.Modal):
    name_input : discord.ui.TextInput
    description_input : discord.ui.TextInput
    image_url_input : ValidImageURLTextInput

    def __init__(
        self,
        *args,
        config: Config,
        guild: discord.Guild,
        race_id: int,
        author_id: int,
        **kwargs,
    ):
        super().__init__(*args, title="Edit Race Details", **kwargs)
        self.config = config
        self.guild = guild
        self.race_id = race_id
        self.author_id = author_id


    async def collect(self) -> "EditRaceDetailsModal":
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        race = next((r for r in races if r['id'] == self.race_id), None)

        if race is None:
            raise ValueError(f"Race not found with id: {self.race_id}")
    
        self.clear_items()
        
        self.name_input = discord.ui.TextInput(
            placeholder="Enter a name for this race.",
            required=True,
            default=race['name'],
            label="Race Name",    
            style=discord.TextStyle.short,
            max_length=100,
        )
        self.description_input = discord.ui.TextInput(
            placeholder="Enter a description for this race.",
            required=True,
            default=race['description'],
            label="Race Description",
            style=discord.TextStyle.long,
        )
        self.image_url_input = ValidImageURLTextInput(
            placeholder="Provide an image link (.png, .jpg, .jpeg, or .gif)",
            required=True,
            default=race['image_url'],
            label="Race Image",    
            style=discord.TextStyle.long,
        )

        self.add_item(self.name_input)
        self.add_item(self.description_input)
        self.add_item(self.image_url_input)

        return self
    
    async def _get_race_config(self) -> Race:
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        found_race = next((r for r in races if r['id'] == self.race_id), None)

        if found_race is None:
            raise ValueError(f"No race found with id: {self.race_id}")
        
        return found_race

    async def _set_race_config(
        self,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        image_url: typing.Optional[str] = None,
    ) -> None:
        async with self.config.guild(self.guild).races.get_lock():
            races : typing.List[Race] = await self.config.guild(self.guild).races()
            race = next((r for r in races if r['id'] == self.race_id), None)

            if race is None:
                raise ValueError(f"No race was found with id: {self.race_id}")
            
            if name is not None:
                race['name'] = name
            if description is not None:
                race['description'] = description
            if image_url is not None:
                race['image_url'] = image_url

            races = [r for r in races if r['id'] != self.race_id]
            races.append(race)
            races.sort(key=lambda r: r['name'])
            
            await self.config.guild(self.guild).races.set(races)
        pass
        

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            raise Exception("You are not the author of this view.")

        return True

    async def on_submit(self, interaction: discord.Interaction):
        name = self.name_input.value
        description = self.description_input.value
        image_url = self.image_url_input.value

        await self._set_race_config(name=name, description=description, image_url=image_url)

        await interaction.response.send_message("Saved changes.", ephemeral=True, delete_after=5)
        self.stop()

class _RacePaginatedEmbed(PaginatedEmbed):
    config : Config
    guild : discord.Guild

    select_list : typing.Optional[OnCallbackSelect] = None

    def __init__(
            self, 
            *args, 
            config : Config,
            interaction : typing.Optional[discord.Interaction] = None,
            original_message : typing.Optional[discord.Message] = None,
            show_stats : bool = False,
            **kwargs
        ):
        if interaction is None and original_message is None:
            raise ValueError("Either interaction or message must be provided.")
                
        async def get_page(index: int) -> typing.Tuple[discord.Embed, int]:
            races : typing.List[Race] = await self.config.guild(self.guild).races()
            
            if not races or len(races) == 0:
                return ( 
                    discord.Embed(
                        title="No Races Found",
                        description=f"There aren't any races found in {self.guild.name}.",
                        color=discord.Color.red()
                    ),
                    0,
                )
            
            return await BattlerRaceEmbed(
                config=self.config,
                guild=self.guild,
                race_id=races[self.index]['id']   
            ).send(show_stats=show_stats), len(races)

        super().__init__(*args, interaction=interaction, message=original_message, get_page=get_page, **kwargs)

        self.config = config
        self.guild = self.interaction.guild if self.interaction else self.original_message.guild # type: ignore[assignment,union-attr]

    async def edit_page(self) -> None:
        _, size = await self.get_page(0)

        if size > 1 and size < DISCORD_MAX_SELECT_OPTIONS:
            races : typing.List[Race] = await self.config.guild(self.guild).races()

            async def edit_selected_page(values: typing.List[str]) -> None:
                self.index = int(values[0])
                await self.edit_page()

            options = [
                discord.SelectOption(
                    label=race['name'],
                    value=str(i),
                )
                for i, race in enumerate(races)
            ]

            if self.select_list is None:
                self.select_list : OnCallbackSelect = OnCallbackSelect(
                    custom_id="race_list",
                    placeholder="Select a race to view.",
                    options=options,
                    callback=edit_selected_page,
                    row=1
                )
                self.add_item(self.select_list)
            else:
                self.select_list.options = options

        elif size <= 1:
            if self.select_list is not None:
                self.remove_item(self.select_list)
                self.select_list = None
            self.previous.disabled = True
            self.next.disabled = True

        await super().edit_page()

    async def send(self) -> "_RacePaginatedEmbed":
        await super().send()

        self.update_buttons()
        await self.edit_page()
        await self.message.edit(view=self)

        return self

class AdminRaceConfigure(discord.ui.View):
    select_modifier : typing.Union[discord.ui.Select, None] = None

    def __init__(
        self, 
        config: Config,
        guild: discord.Guild,
        message: discord.Message,
        author_id: int,
        race_id: int,
    ):
        super().__init__()
        self.config = config
        self.guild = guild
        self.race_id = race_id
        self.author_id = author_id
        self.message = message

    async def collect(self) -> "AdminRaceConfigure":
        race = await self._get_config()
        
        self.clear_items()

        self.add_item(self.edit_details)

        self.add_item(self.add_modifier)

        if len(race['modifiers']) >= 1:
            self.edit_modifier.disabled = False
            self.delete_modifier.disabled = False

            self.add_item(self.edit_modifier)
            self.add_item(self.delete_modifier)

            async def return_none(_): return None

            if len(race['modifiers']) >= 2:
                self.select_modifier : OnCallbackSelect = OnCallbackSelect(
                    max_values=1,
                    placeholder="Select a modifier to edit or delete.",
                    options=[
                        discord.SelectOption(
                            label=f"{modifier['key']} ({modifier['operator']} {modifier['value']})",
                            value=str(i),
                        )
                        for i, modifier in enumerate(race['modifiers'])
                    ],
                    row=2,
                    callback=return_none
                )

                self.add_item(self.select_modifier)

        self.add_item(self.save)

        return self

    async def _get_config(self) -> Race:
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        found_race = next((r for r in races if r['id'] == self.race_id), None)
        if found_race is None:
            raise ValueError(f"No race was found with id: `{self.race_id}`.")
        
        return found_race
    
    async def _set_config(
        self,
        name: typing.Optional[str] = None,
        description: typing.Optional[str] = None,
        image_url: typing.Optional[str] = None,
        modifiers: typing.Optional[typing.List[Modifier]] = None,

    ) -> None:
        async with self.config.guild(self.guild).races.get_lock():
            races : typing.List[Race] = await self.config.guild(self.guild).races()
            found_race = next((r for r in races if r['id'] == self.race_id), None)

            if found_race is None:
                raise ValueError("Cannot create a race with missing fields.")

            if name is not None:
                found_race['name'] = name
            if description is not None:
                found_race['description'] = description
            if image_url is not None:
                found_race['image_url'] = image_url
            if modifiers is not None:
                found_race['modifiers'] = modifiers

            races = [r for r in races if r['id'] != self.race_id]
            races.append(found_race)
            races.sort(key=lambda r: r['name'])
            
            await self.config.guild(self.guild).races.set(races)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            raise Exception("You are not the author of this view.")

        return True
    
    @discord.ui.button(label="Edit Details", style=discord.ButtonStyle.secondary, row=0)
    async def edit_details(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = await EditRaceDetailsModal(
            config=self.config,
            guild=self.guild,
            author_id=self.author_id,
            race_id=self.race_id,
        ).collect()

        await interaction.response.send_modal(modal)
        if await modal.wait():
            return
        
        await self.message.edit(embed=await BattlerRaceEmbed(
            config=self.config,
            guild=self.guild,
            race_id=self.race_id,
        ).send(), view=self)

    @discord.ui.button(label="Add Modifier", style=discord.ButtonStyle.green, row=1)
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

        await self.message.edit(embed=await BattlerRaceEmbed(
            config=self.config,
            guild=self.guild,
            race_id=self.race_id,
        ).send(), view=self)

        pass

    @discord.ui.button(label="Edit Modifier", style=discord.ButtonStyle.secondary, disabled=True, row=1)
    async def edit_modifier(self, interaction: discord.Interaction, button: discord.ui.Button):
        config : Race = await self._get_config()

        index = 0

        if self.select_modifier is not None:
            index = int(self.select_modifier.values[0])

        modifiers = config['modifiers']
        modifier = modifiers[index]

        view = await EditModifierView(
            config=self.config,
            interaction=interaction,
            modifier=modifier
        ).send()
        
        if await view.wait() or not view.is_confirmed:
            return
        
        modifiers[index] = view.modifier
        
        await self._set_config(modifiers=modifiers)

        await self.collect()

        await self.message.edit(embed=await BattlerRaceEmbed(
            config=self.config,
            guild=self.guild,
            race_id=self.race_id,
        ).send(), view=self)

        pass

    @discord.ui.button(label="Delete Modifier", style=discord.ButtonStyle.danger, disabled=True, row=1)
    async def delete_modifier(self, interaction: discord.Interaction, button: discord.ui.Button):
        race = await self._get_config()
        
        if self.select_modifier is None:
            index = 0
        else:
            index = int(self.select_modifier.values[0])

        modifier = race['modifiers'].pop(index)

        await self._set_config(modifiers=race['modifiers'])

        await self.collect()

        await interaction.response.send_message(f"Deleted modifier: {modifier['key']} ({modifier['operator']} {modifier['value']}).", ephemeral=True, delete_after=10)

        await self.message.edit(embed=await BattlerRaceEmbed(
            config=self.config,
            guild=self.guild,
            race_id=self.race_id,
        ).send(), view=self)

        pass
    
    @discord.ui.button(label="Done Editing", style=discord.ButtonStyle.primary, row=4)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.stop()

class AdminRacePaginatedEmbed(_RacePaginatedEmbed):
    def __init__(
            self, 
            *args, 
            config : Config,
            interaction : typing.Optional[discord.Interaction] = None,
            original_message : typing.Optional[discord.Message] = None,
            **kwargs
        ):
        super().__init__(
            *args, 
            config=config, 
            interaction=interaction, 
            original_message=original_message, 
            show_stats=True,
            **kwargs
        )

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            raise Exception("You are not the author of this view.")

        return await super().interaction_check(interaction)

    @discord.ui.button(label="Add New", style=discord.ButtonStyle.primary, row=2)
    async def add_new(self, interaction: discord.Interaction, button: discord.ui.Button):
        races : typing.List[Race] = await self.config.guild(self.guild).races()

        new_race : Race = {
            'id': uuid.uuid4().int,
            'name': DEFAULT_NAME,
            'description': DEFAULT_DESCRIPTION,
            'image_url': DEFAULT_IMAGE_URL,
            'modifiers': [],
        }

        races.append(new_race)

        await self.config.guild(self.guild).races.set(races)

        self.index = len(races) - 1

        await self.edit_page()

        await interaction.response.defer()

        view = await AdminRaceConfigure(
            config=self.config,
            guild=self.guild,
            message=self.message,
            race_id=new_race['id'],
            author_id=self.author.id
        ).collect()
        
        await self.message.edit(view=view)
        await view.wait()

        await self.edit_page()

        pass

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, row=2)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        race = races[self.index]

        await interaction.response.defer()

        view = await AdminRaceConfigure(
            config=self.config,
            guild=self.guild,
            message=self.message,
            race_id=race['id'],
            author_id=self.author.id
        ).collect()
        
        await self.message.edit(view=view)
        await view.wait()

        await self.edit_page()
        pass

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, row=2)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        race = races.pop(self.index)

        if self.index == 0:
            await interaction.response.send_message(f"ERROR: Cannot delete base race `{race['name']}`.", ephemeral=True, delete_after=10)
            return
        
        default_member = self.config.defaults['MEMBER']

        view = ConfirmationView(author=interaction.user) # type: ignore[arg-type]

        await interaction.response.send_message(
            content=f"Are you sure you want to delete `{race['name']}`? All existing members will be transfered to `{races[default_member['race_id']]['name']}`",
            view=view,
            ephemeral=True,
        )

        if await view.wait() or not view.value:
            await interaction.delete_original_response()
            return

        member_data : typing.Dict[int, BattleUserConfig] = await self.config.all_members(self.guild)
        filtered_members = {
            id: data
            for id, data in member_data.items()
            if data['race_id'] == race['id']
        }

        async with self.config.get_members_lock(self.guild):
            for id, _ in filtered_members.items():
                await self.config.member_from_ids(self.guild.id, id).race_id.set(default_member['race_id'])
                await self.config.member_from_ids(self.guild.id, id).race_chosen.set(default_member['race_chosen'])

        await self.config.guild(self.guild).races.set(races)

        await interaction.response.edit_message(content=f"Deleted `{race['name']} ({race['id']}).", delete_after=10)

        self.index = max(self.index - 1, 0)

        await self.edit_page()

        pass

class SelectRacePaginatedEmbed(_RacePaginatedEmbed):
    def __init__(
            self, 
            *args, 
            config : Config,
            interaction : typing.Optional[discord.Interaction] = None,
            original_message : typing.Optional[discord.Message] = None,
            **kwargs
        ):
        super().__init__(
            *args, 
            config=config, 
            interaction=interaction, 
            original_message=original_message, 
            show_stats=False,
            **kwargs
        )

    async def send(self) -> "SelectRacePaginatedEmbed":
        await super().send()

        await self.message.edit(content="Select a race to choose from the list:")

        return self

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author.id:
            raise Exception("You are not the author of this view.")

        if await self.config.member(interaction.user).race_chosen():                        # type: ignore[arg-type]
            races : typing.List[Race] = await self.config.guild(self.guild).races()
            chosen_race = races[await self.config.member(interaction.user).race_id()]       # type: ignore[arg-type]
            raise Exception(f"You have already chosen a race: `{chosen_race['name']}`")

        return await super().interaction_check(interaction)

    @discord.ui.button(label="Select", style=discord.ButtonStyle.primary, row=2)
    async def select(self, interaction: discord.Interaction, button: discord.ui.Button):
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        chosen_config = races[self.index]

        view = ConfirmationView(author=interaction.user) # type: ignore[arg-type]

        await interaction.response.send_message(f"Are you sure you want to choose `{chosen_config['name']}`?", ephemeral=True, view=view)
        
        if await view.wait() or not view.value:
            await interaction.delete_original_response()
            return
        
        await self.config.member(interaction.user).race_id.set(chosen_config['id'])     # type: ignore[arg-type]
        await self.config.member(interaction.user).race_chosen.set(True)                # type: ignore[arg-type]

        await interaction.delete_original_response()

        self.stop()
        await self.message.edit(content=None, view=None)