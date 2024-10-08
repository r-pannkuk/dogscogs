import typing
import discord
from redbot.core import commands, bank

class KarmaEmbed(discord.Embed):
    def __init__(
            self, 
            ctx: commands.GuildContext, 
            *, 
            title: str,
            sticker_counts: typing.Dict[str, int],
            karma: float,
            rating: str
        ):
        if rating == "Good":
            color = discord.Color.from_rgb(225,180,180)
            url = 'https://puppy-bot.com/remibot/media/remilia_good.webp'
        elif rating == "Lawful Good":
            color = discord.Color.from_rgb(255,180,180)
            url = 'https://puppy-bot.com/remibot/media/remilia_lawful_good.png'
        elif rating == "Evil":
            color = discord.Color.purple()
            url = "https://puppy-bot.com/remibot/media/remilia_evil2.png"
        elif rating == "Chaotic Evil":
            color = discord.Color.dark_purple()
            url = "https://puppy-bot.com/remibot/media/remilia_chaotic_evil.png"
        elif rating == "Neutral":
            color = discord.Color.from_rgb(205,200,237)
            url = "https://puppy-bot.com/remibot/media/remilia_neutral.jpg"
        super().__init__(
            title=title,
            color=color
        )
        self.set_thumbnail(url=url)
        guild = ctx.guild
        counts = ""
        for sticker_id, count in sticker_counts.items():
            sticker : typing.Union[discord.Sticker, None] = next((sticker for sticker in guild.stickers if sticker.id == int(sticker_id)), None)
            if sticker is None:
                continue

            counts += f"`{sticker.name}` used {count} time{'s' if count > 1 else ''}\n"

        self.description = f"Karma: {karma:.0%}\nRating: {rating}\n\n{counts}"

        pass