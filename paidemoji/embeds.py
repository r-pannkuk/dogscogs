import typing
import discord
from redbot.core import commands

from .paidemoji import PaidEmojiConfig

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