from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER

DEFAULT_BET_TITLE = "New Bet"
DEFAULT_BET_DESCRIPTION = "This is a new bet."

from .config import BetGuildConfig, BetConfig, generate_bet_config
from .views import BetAdministrationView
from .embed import BetEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD : BetGuildConfig = {
    "enabled": True,
    "active_bets": {},
}

class Bets(commands.Cog):
    """
    Set up bets for tournament matchups and others.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)

    @commands.group()
    @commands.guild_only()
    async def bet(self, ctx: commands.GuildContext):
        """
        Set up bets for tournament matchups and others.
        """
        pass

    @bet.command()
    @commands.guild_only()
    async def list(self, ctx: commands.GuildContext):
        """
        List all active bets.
        """
        pass

    @bet.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def create(self, ctx: commands.GuildContext):
        """
        Create a new bet.
        """
        active_bets : typing.Dict[str, BetConfig] = await self.config.guild(ctx.guild).active_bets()
        new_config : BetConfig = generate_bet_config(
            author_id=ctx.author.id,
            title=DEFAULT_BET_TITLE,
            description=DEFAULT_BET_DESCRIPTION,
        )
        active_bets.update({str(new_config['id']): new_config})
        await self.config.guild(ctx.guild).active_bets.set(active_bets)

        original_message = await ctx.send(embed=await BetEmbed(
            bet_config_id=new_config['id'],
            config=self.config,
            ctx=ctx,
        ).generate())
        view = await BetAdministrationView(
            original_message=original_message,
            config=self.config,
            ctx=ctx,
            bet_config_id=new_config['id'],
        ).generate()
        await original_message.edit(view=view)

        pass


