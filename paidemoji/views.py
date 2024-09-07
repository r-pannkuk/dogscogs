import re
import typing
import discord
from redbot.core import commands

from paidemoji.classes import PaidEmojiType

EMOJI_NAME_LENGTH_MIN = 2
EMOJI_NAME_LENGTH_MAX = 32
EMOJI_NAME_VALID_REGEX = r"^[a-zA-Z0-9_]+$"
EMOJI_URL_VALID_REGEX = r"(http(s?):)([/|.|\w|\s|-])*\.(?:jpg|jpeg|gif|png)"

class EmojiConfigurationModal(discord.ui.Modal):
    name_field : discord.ui.TextInput = discord.ui.TextInput(required=True, custom_id="emoji_name", label="Name", style=discord.TextStyle.short, placeholder=":emoji_name:")
    url_field : discord.ui.TextInput = discord.ui.TextInput(required=True, custom_id="emoji_url", label="URL", style=discord.TextStyle.paragraph, placeholder="https://example.com/emoji.png")

    name: str
    url: str
    type: PaidEmojiType

    successful : bool = False

    def __init__(self, ctx: commands.GuildContext):
        super().__init__(title="New Paid Emoji", timeout=60*10)
        self.ctx = ctx
        self.author = ctx.author
        pass

    @staticmethod
    def _strip_emoji_name(name: str) -> str:
        if name.startswith(':') and name.endswith(':'):
            name = name[1:-1]
        name = name.lower()
        return name
    

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            raise ValueError("You are not allowed to interact with this message.")

        if not self.name_field.value or not self.url_field.value:
            raise ValueError("Both fields are required.")
        
        name = self.name_field.value
        
        if name and name:
            name = name[1:-1]

        if len(name) < EMOJI_NAME_LENGTH_MIN or len(name) > EMOJI_NAME_LENGTH_MAX:
            raise ValueError(f"Emoji name must be between {EMOJI_NAME_LENGTH_MIN} and {EMOJI_NAME_LENGTH_MAX} characters.")
        
        if re.match(EMOJI_NAME_VALID_REGEX, name) is None:
            raise ValueError("Emoji name must be alphanumeric with no spaces.")
        
        if re.match(EMOJI_URL_VALID_REGEX, self.url_field.value) is None:
            raise ValueError("Invalid URL.")

        return True
    
    async def on_error(self, interaction, error):
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True, delete_after=10
        )
        pass

    async def on_submit(self, interaction: discord.Interaction):
        self.name = EmojiConfigurationModal._strip_emoji_name(self.name_field.value)
        self.url = self.url_field.value
        self.type = 'animated' if self.url.endswith(".gif") else 'image'
        self.successful = True
        await interaction.response.defer()
    