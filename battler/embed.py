import discord
from redbot.core.bot import Red
from redbot.core.config import Config

from .config import BattleUserConfig

class BattlerStatusEmbed(discord.Embed):
    def __init__(self, battler: BattleUserConfig):
        pass

class BattlerConfigEmbed(discord.Embed):
    def __init__(
            self, 
            client: Red, 
            config: Config, 
            guild: discord.Guild
        ):
        super().__init__(
            title=f"{guild.name} Battler Configuration", 
            color=discord.Color.green()
        )
        self.config = config
        self.client = client
        self.guild = guild
        self.group = config.guild(guild)

    async def collect(self):
        pass