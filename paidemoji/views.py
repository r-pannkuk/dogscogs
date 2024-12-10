import re
import typing
import emoji as emoji_module
import discord
from redbot.core import commands

from dogscogs.constants.discord.emoji import MAX_NAME_LENGTH as EMOJI_MAX_NAME_LENGTH, MIN_NAME_LENGTH as EMOJI_MIN_NAME_LENGTH
from dogscogs.constants.regex import EMOJI_NAME as REGEX_EMOJI_NAME, EMOJI_URL as REGEX_EMOJI_URL

from paidemoji.classes import PaidEmojiType

STICKER_MIN_NAME_LENGTH = 2
STICKER_MAX_NAME_LENGTH = 30

STICKER_MIN_DESCRIPTION_LENGTH = 0
STICKER_MAX_DESCRIPTION_LENGTH = 100

def strip_emoji_name(name: str) -> str:
    if name.startswith(':') and name.endswith(':'):
        name = name[1:-1]
    name = name.lower()
    return name

class StickerConfigurationModal(discord.ui.Modal):
    url_field : discord.ui.TextInput = discord.ui.TextInput(required=True, custom_id="sticker_url", label="URL", style=discord.TextStyle.paragraph, placeholder="https://example.com/sticker.png")
    emoji_field : discord.ui.TextInput = discord.ui.TextInput(required=True, custom_id="emoji_name", label="Emoji", style=discord.TextStyle.short, placeholder=":emoji_name:")
    name_field : discord.ui.TextInput = discord.ui.TextInput(required=True, custom_id="sticker_name", label="Name", max_length=STICKER_MAX_NAME_LENGTH, min_length=STICKER_MIN_NAME_LENGTH, style=discord.TextStyle.short, placeholder="StickerName")
    description_field : discord.ui.TextInput = discord.ui.TextInput(required=False, custom_id="sticker_description", label="Description", style=discord.TextStyle.paragraph, max_length=STICKER_MAX_DESCRIPTION_LENGTH, placeholder="A description of the sticker.")

    name: str
    description: str
    url: str
    emoji: str

    successful : bool = False

    def __init__(self, ctx: commands.GuildContext):
        super().__init__(title="New Paid Sticker", timeout=60*10)
        self.ctx = ctx
        self.author = ctx.author
        pass
    

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            raise ValueError("You are not allowed to interact with this message.")

        if not self.name_field.value or not self.url_field.value or not self.emoji_field.value:
            raise ValueError("All fields are required.")
        

        if len(self.name_field.value) < STICKER_MIN_NAME_LENGTH or len(self.name_field.value) > STICKER_MAX_NAME_LENGTH:
            raise ValueError(f"Sticker name must be between {STICKER_MIN_NAME_LENGTH} and {STICKER_MAX_NAME_LENGTH} characters.")
        
        emoji_name = strip_emoji_name(self.emoji_field.value)

        found_match = False

        for emoji in interaction.guild.emojis:
            if emoji.name == emoji_name:
                found_match = True
                break

        if emoji_module.is_emoji(emoji_name):
            found_match = True

        discord_unicode_emoji_names = [strip_emoji_name(value['en'].lower()) for _, value in emoji_module.EMOJI_DATA.items()]  # List of supported names
        if strip_emoji_name(emoji_name.lower()) in discord_unicode_emoji_names:
            return True

        if not found_match:
            raise ValueError("Emoji does not exist in this server nor is it a unicode emoji.")

        
        if re.match(REGEX_EMOJI_URL, self.url_field.value) is None:
            raise ValueError("Invalid URL.")

        return True
    
    async def on_error(self, interaction, error):
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True, delete_after=10
        )
        pass

    async def on_submit(self, interaction: discord.Interaction):
        self.name = self.name_field.value
        self.description = self.description_field.value
        self.emoji = strip_emoji_name(self.emoji_field.value.lower())
        self.url = self.url_field.value
        self.successful = True
        await interaction.response.defer()
    

class EmojiConfigurationModal(discord.ui.Modal):
    name_field : discord.ui.TextInput = discord.ui.TextInput(required=True, custom_id="emoji_name", label="Name", min_length=EMOJI_MIN_NAME_LENGTH, max_length=EMOJI_MAX_NAME_LENGTH, style=discord.TextStyle.short, placeholder=":emoji_name:")
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
    

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user != self.ctx.author:
            raise ValueError("You are not allowed to interact with this message.")

        if not self.name_field.value or not self.url_field.value:
            raise ValueError("Both fields are required.")
        
        name = strip_emoji_name(self.name_field.value)

        if len(name) < EMOJI_MIN_NAME_LENGTH or len(name) > EMOJI_MAX_NAME_LENGTH:
            raise ValueError(f"Emoji name must be between {EMOJI_MIN_NAME_LENGTH} and {EMOJI_MAX_NAME_LENGTH} characters.")
        
        if re.match(REGEX_EMOJI_NAME, name) is None:
            raise ValueError("Emoji name must be alphanumeric with no spaces.")
        
        if re.match(REGEX_EMOJI_URL, self.url_field.value) is None:
            raise ValueError("Invalid URL.")

        return True
    
    async def on_error(self, interaction, error):
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True, delete_after=10
        )
        pass

    async def on_submit(self, interaction: discord.Interaction):
        self.name = strip_emoji_name(self.name_field.value)
        self.url = self.url_field.value
        self.type = 'animated' if self.url.endswith(".gif") else 'image'
        self.successful = True
        await interaction.response.defer()
    