from typing import Literal
import typing

import discord
import shlex
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.core.converter import DogCogConverter

DEFAULT_BET_TITLE = "New Bet"
DEFAULT_BET_DESCRIPTION = "This is a new bet."
KEY_OPERATORs = ["=", ":"]

from .config import BetGuildConfig, BetConfig, generate_bet_config
from .views import BetAdministrationView, BetListPaginatedEmbed
from .embed import BetEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD : BetGuildConfig = {
    "enabled": True,
    "active_bets": {},
    "allowed_role_ids": [],
}

class BetConfigFields(BetConfig, total=False):
    pass

class SearchCriteria(DogCogConverter):
    @staticmethod
    async def parse(ctx: commands.Context, argument: str) -> typing.Union[BetConfigFields, None]:
        if argument == "":
            return None
        
        retval = BetConfigFields() #type: ignore

        for part in shlex.split(argument):
            parsed_part = part
            if part.startswith("--"):
                parsed_part = part[2:]
            elif part.startswith("-"):
                parsed_part = part[1:]

            if any(parsed_part.lower().startswith(field) for field in BetConfigFields.__annotations__):
                for operator in KEY_OPERATORs:
                    if operator in parsed_part:
                        key, value = parsed_part.split(operator, 1)
                        if key.lower() in BetConfigFields.__annotations__:
                            retval[key.lower()] = value

        return retval

async def permissions_check(ctx: commands.Context) -> bool:
    config = Config.get_conf(
        None,
        identifier=COG_IDENTIFIER,
        force_registration=True,
        cog_name="Bets",
    )

    if ctx.guild is None:
        return False

    if not await config.guild(ctx.guild).enabled():
        await ctx.send("Bets are not enabled in this server.")
        return False

    if ctx.author.guild_permissions.manage_roles: # type: ignore[union-attr]
        return True

    allowed_role_ids = await config.guild(ctx.guild).allowed_role_ids()
    if any(role.id in allowed_role_ids for role in ctx.author.roles): # type: ignore[union-attr]
        return True

    return False

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
    @commands.permissions_check(permissions_check)
    async def bet(self, ctx: commands.GuildContext):
        """
        Set up bets for tournament matchups and others.
        """
        pass

    @commands.group()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def enabled(self, ctx: commands.GuildContext, bool: typing.Optional[bool]):
        """
        Enable or disable bets in the server.
        """
        if bool is None:
            bool = not await self.config.guild(ctx.guild).enabled()

        await self.config.guild(ctx.guild).enabled.set(bool)
        await ctx.send(f"Bets are {'`ENABLED`' if bool else '`DISABLED`'}.")

    @bet.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def roles(self, ctx: commands.GuildContext, roles: typing.Annotated[typing.List[discord.Role], commands.Greedy[discord.Role]]):
        if len(roles) == 0:
            role_ids = await self.config.guild(ctx.guild).allowed_role_ids()
            roles = [role for role in [ctx.guild.get_role(role_id) for role_id in role_ids] if role is not None]

        await self.config.guild(ctx.guild).allowed_role_ids.set([role.id for role in roles])
        
        if len(roles) == 0:
            await ctx.send("Only elevated users are allowed to create and manage bets.")
            return
        
        await ctx.send(f"Allowed roles set to: {', '.join([role.mention for role in roles])}")


    @bet.command()
    @commands.guild_only()
    @commands.permissions_check(permissions_check) # type: ignore[arg-type]
    async def list(self, ctx: commands.GuildContext, *, search: typing.Optional[typing.Annotated[BetConfigFields, SearchCriteria]] = None):
        """
        List all active bets.

        Provide a search filter to find explicit bets.

        Example:
        - `[p]bet list --state=open`

        Available search fields:
        - `state`
        - `author_id`
        - `title`
        - `description`
        - `base_value`
        - `minimum_bet`
        - `options`
        """
        if search is None or search == {}:
            paginated_embed = BetListPaginatedEmbed(
                config=self.config,
                ctx=ctx,
            )
        else:
            paginated_embed = BetListPaginatedEmbed(
                config=self.config,
                ctx=ctx,
                filter=lambda x: all(str(value).lower() in str(x[field]).lower() for field, value in search.items() if value != "") # type: ignore[literal-required]
            )
        
        await paginated_embed.send()

        if paginated_embed.total_pages == 0:
            await ctx.send("No bets found with the provided search criteria.")
            return

        if await paginated_embed.wait():
            return
        
        await paginated_embed.message.edit(view=await BetAdministrationView(
            original_message=paginated_embed.message,
            config=self.config,
            ctx=ctx,
            bet_config_id=paginated_embed.bet_config['id'],
        ).generate())
        pass

    @bet.command()
    @commands.guild_only()
    @commands.permissions_check(permissions_check) # type: ignore[arg-type]
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


