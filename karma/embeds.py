import typing
import discord
from redbot.core import commands, bank

class KarmaEmbed(discord.Embed):
    def __init__(
            self, 
            ctx: commands.Context, 
            *, 
            title: str,
            sticker_counts: typing.Dict[str, typing.List[int]],
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
        for sticker_id, messages in sticker_counts.items():
            sticker : discord.Sticker = next((sticker for sticker in guild.stickers if sticker.id == int(sticker_id)), None)
            if sticker == None:
                continue

            counts += f"`{sticker.name}` used {len(messages)} time{'s' if len(messages) > 1 else ''}\n"

        self.description = f"Karma: {karma:.0%}\nRating: {rating}\n\n{counts}"

        pass