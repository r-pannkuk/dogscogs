import typing
import uuid
import discord
from redbot.core.config import Config

from dogscogs.views.paginated import PaginatedEmbed, OnCallbackSelect
from dogscogs.constants.discord.views import MAX_SELECT_OPTIONS as DISCORD_MAX_SELECT_OPTIONS

from .embed import BattlerRaceEmbed

from .config import Modifier, Race

DEFAULT_NAME = "<NAME>"
DEFAULT_DESCRIPTION = "<DESCRIPTION>"
DEFAULT_IMAGE_URL = "https://en.touhouwiki.net/images/a/a6/Th06Windmill.png"

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

    async def send(self) -> None:
        await super().send()

        self.update_buttons()
        await self.edit_page()
        await self.message.edit(view=self)

class AdminRaceConfigure(discord.ui.View):
    def __init__(
        self, 
        config: Config,
        guild: discord.Guild,
        author_id: int,
        race_id: int,
    ):
        super().__init__()
        self.config = config
        self.guild = guild
        self.race_id = race_id
        self.author_id = author_id

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

            races = [r for r in races if r['id'] != id]
            races.append(found_race)

            await self.config.guild(self.guild).races.set(races)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            raise Exception("You are not the author of this view.")

        return True
    
    @discord.ui.button(label="Save", style=discord.ButtonStyle.primary, row=4)
    async def save(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Saved changes.", ephemeral=True, delete_after=5)
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

        view = AdminRaceConfigure(
            config=self.config,
            guild=self.guild,
            race_id=new_race['id'],
            author_id=self.author.id
        )
        
        await self.message.edit(view=view)
        await view.wait()

        await self.edit_page()

        pass

    @discord.ui.button(label="Edit", style=discord.ButtonStyle.secondary, row=2)
    async def edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        pass

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger, row=2)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        races : typing.List[Race] = await self.config.guild(self.guild).races()
        race = races.pop(self.index)
        await self.config.guild(self.guild).races.set(races)

        await interaction.response.send_message(f"Deleted `{race['name']} ({race['id']}).", ephemeral=True, delete_after=10)

        self.index = max(self.index - 1, 0)

        await self.edit_page()

        pass