import typing
import discord

class PaginatedEmbed(discord.ui.View):
    message : discord.Message

    def __init__(
            self,
            *,
            message : typing.Optional[discord.Message] = None,
            interaction : typing.Optional[discord.Interaction] = None,
            get_page: typing.Callable[[int], typing.Awaitable[typing.Tuple[discord.Embed, int]]]
    ):
        self.original_message : typing.Optional[discord.Message] = message
        self.interaction : typing.Optional[discord.Interaction] = interaction

        if self.original_message is None and self.interaction is None:
            raise ValueError("Either message or interaction must be provided.")
    
        if self.original_message is not None:
            self.author = self.original_message.author
        if self.interaction is not None:
            self.author = self.interaction.user

        self.get_page : typing.Callable[[int], typing.Awaitable[typing.Tuple[discord.Embed, int]]] = get_page
        self.total_pages : int = 0
        self.index = 0
        super().__init__(timeout=10*60)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user == self.author:
            return True
        else:
            await interaction.response.send_message("You are not allowed to interact with this view.", ephemeral=True, delete_after=10)
            return False
        
    async def send(self):
        embed, self.total_pages = await self.get_page(self.index)
        if self.total_pages == 1:
            if self.original_message is not None:
                self.message = await self.original_message.reply(embed=embed, view=None)
            elif self.interaction is not None:
                self.message = await self.interaction.response.send_message(embed=embed)
        elif self.total_pages > 1:
            self.update_buttons()
            if self.original_message is not None:
                self.message = await self.original_message.reply(embed=embed, view=self)
            elif self.interaction is not None:
                self.message = await self.interaction.response.send_message(embed=embed, view=self)

    async def edit_page(self):
        embed, self.total_pages = await self.get_page(self.index)
        self.update_buttons()
        await self.message.edit(embed=embed, view=self)

    def update_buttons(self):
        self.children[0].disabled = self.index == 0
        self.children[3].disabled = self.index == self.total_pages - 1
        pass

    @discord.ui.button(emoji="⏪", style=discord.ButtonStyle.secondary)
    async def first(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index = 0
            await self.edit_page()
        await interaction.response.defer()

    @discord.ui.button(emoji="◀️", style=discord.ButtonStyle.blurple)
    async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index > 0:
            self.index -= 1
            await self.edit_page()
        elif self.index == 0:
            self.index = self.total_pages - 1
            await self.edit_page()
        await interaction.response.defer()

    @discord.ui.button(emoji="▶️", style=discord.ButtonStyle.blurple)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < self.total_pages - 1:
            self.index += 1
            await self.edit_page()
        elif self.index == self.total_pages - 1:
            self.index = 0
            await self.edit_page()
        await interaction.response.defer()

    @discord.ui.button(emoji="⏩", style=discord.ButtonStyle.secondary)
    async def last(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.index < self.total_pages - 1:
            self.index = self.total_pages - 1
            await self.edit_page()
        await interaction.response.defer()

    async def on_timeout(self):
        await self.message.edit(view=None)

    @staticmethod
    def compute_total_pages(total_results: int, results_per_page: int) -> int:
        return ((total_results - 1) // results_per_page) + 1

    