import typing
import discord
from redbot.core import commands

from .paidemoji import PaidEmojiConfig, PaidStickerConfig

class PaidEmojiEmbed(discord.Embed):
    emoji : typing.Union[discord.Emoji, None]
    emoji_config : PaidEmojiConfig
    emoji_author : typing.Union[discord.Member, discord.User, None]

    def __init__(
        self, 
        *, 
        ctx: commands.GuildContext, 
        emoji_config: PaidEmojiConfig,
    ):
        self.emoji = ctx.guild.get_emoji(emoji_config["id"])
        self.emoji_config = emoji_config
        self.emoji_author = ctx.guild.get_member(emoji_config["author_id"])

        if self.emoji_author is None:
            ctx.bot.get_user(emoji_config["author_id"])

        if self.emoji is None:
            super().__init__(title=f"Emoji {emoji_config['id']} not found", description="This emoji was deleted.")
            return
        
        super().__init__(title=self.emoji.name)
        
        self.description = ""
        self.description += f"__Name__: {discord.utils.escape_markdown(self.emoji.name)}\n"
        self.description += f"__ID__: {self.emoji.id}\n"
        self.description += f"__Type__: {self.emoji_config['type']}\n"
        self.description += f"__Source URL__: [Link]({self.emoji_config['source_url']})\n"
        self.description += f"__Price__: {self.emoji_config['price']}\n"
        self.description += f"\n"
        self.description += f"__Used Count__: {self.emoji_config['used_count']}\n"
        self.description += f"__Last Used At__: <t:{int(self.emoji_config['last_used_at'])}:F>\n"
        self.description += f"__Created By__: {self.emoji_author.mention if self.emoji_author else 'Unknown'}\n"
        self.description += f"__Created At__: <t:{int(self.emoji.created_at.timestamp())}:F>\n"

        self.set_thumbnail(url=self.emoji.url)



class PaidStickerEmbed(discord.Embed):
    sticker : typing.Union[discord.Sticker, None]
    sticker_config : PaidStickerConfig
    sticker_author : typing.Union[discord.Member, discord.User, None]

    def __init__(
        self, 
        *, 
        ctx: commands.GuildContext, 
        sticker_config: PaidStickerConfig,
    ):
        self.sticker = discord.utils.get(ctx.guild.stickers, id=int(sticker_config['id']))
        self.sticker_config = sticker_config
        self.sticker_author = ctx.guild.get_member(sticker_config["author_id"])

        if self.sticker_author is None:
            ctx.bot.get_user(sticker_config["author_id"])

        if self.sticker is None:
            super().__init__(title=f"Sticker {sticker_config['id']} not found", description="This sticker was deleted.")
            return
        
        super().__init__(title=self.sticker.name)
        
        self.description = ""
        self.description += f"__Name__: {discord.utils.escape_markdown(self.sticker.name)}\n"
        self.description += f"__ID__: {self.sticker.id}\n"
        self.description += f"__Description__: {discord.utils.escape_markdown(self.sticker.description)}\n"
        self.description += f"__Emoji__: {discord.utils.escape_markdown(self.sticker.emoji)}\n"
        self.description += f"__Source URL__: [Link]({self.sticker_config['source_url']})\n"
        self.description += f"__Price__: {self.sticker_config['price']}\n"
        self.description += f"\n"
        self.description += f"__Used Count__: {self.sticker_config['used_count']}\n"
        self.description += f"__Last Used At__: <t:{int(self.sticker_config['last_used_at'])}:F>\n"
        self.description += f"__Created By__: {self.sticker_author.mention if self.sticker_author else 'Unknown'}\n"
        self.description += f"__Created At__: <t:{int(self.sticker.created_at.timestamp())}:F>\n"

        self.set_thumbnail(url=self.sticker.url)