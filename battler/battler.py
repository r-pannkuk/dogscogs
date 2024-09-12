from datetime import datetime, timedelta
import random
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

import d20  # type: ignore[import-untyped]

from dogscogs.constants import COG_IDENTIFIER, TIMEZONE
from dogscogs.core.converter import DogCogConverter

from .config import BattlerConfig, BattleUserConfig, KeyType, Race
from .classes import BattleUser, ApplyModifiers

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD: BattlerConfig = {
    "attacker_wins_ties": True,
    "attacker_roll": "1d20",
    "defender_roll": "1d20",
    "races": [
        {
            "id": 0,
            "name": "Human",
            "description": "Humans are boring.",
            "modifiers": [],
        },
    ],
    "equipment": [],
}

DEFAULT_MEMBER: BattleUserConfig = {
    "equipment_ids": [],
    "race_id": 0,
}

class RaceConverter(DogCogConverter):
    @staticmethod
    async def parse(ctx: commands.GuildContext, argument: str) -> Race: # type: ignore[override]
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Battler",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        try:
            guild_races : typing.List[Race] = await config.guild(ctx.guild).races()
            return next(r for r in guild_races if r['name'].lower() == argument.lower()) 
        except StopIteration:
            raise commands.BadArgument(f"`{argument}` is not a Race found in {ctx.guild.name} Battler configuration.")

class Battler(commands.Cog):
    """
    A battle system with equipment for completing actions.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        self.config.register_guild(**DEFAULT_GUILD)
        self.config.register_member(**DEFAULT_MEMBER)

    @staticmethod
    async def _get(member: discord.Member) -> BattleUser:
        """Returns a read-only copy of the member's battler configuration."""
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Battler",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        return await BattleUser(config=config, member=member).collect()

    @staticmethod
    async def _battle(
        attacker: discord.Member,
        defender: discord.Member,
        *,
        battle_types: typing.List[KeyType]
    ) -> typing.Tuple[d20.RollResult, d20.RollResult, discord.Member]:
        """Does battle between two members.

        Args:
            attacker (discord.Member): The instigator of the attack.
            defender (discord.Member): The one defending for themselves.
            battle_types (typing.List[KeyType]): A list of modifier keys that should be applied for any equipment or other bonuses.

        Returns:
            (d20.RollResult, d20.RollResult, discord.Member): The attacker's roll, the defender's roll, and the winner.
        """
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Battler",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        guild : discord.Guild = attacker.guild

        attacker_battle_user = await Battler._get(attacker)
        defender_battle_user = await Battler._get(defender)

        attacker_roll = await config.guild(guild).attacker_roll()
        defender_roll = await config.guild(guild).defender_roll()

        attacker_roll = ApplyModifiers(attacker_roll, attacker_battle_user, battle_types)
        defender_roll = ApplyModifiers(defender_roll, defender_battle_user, battle_types)

        attacker_result = d20.roll(attacker_roll)
        defender_result = d20.roll(defender_roll)

        if await config.guild(guild).attacker_wins_ties():
            def predicate(x, y):
                return x >= y
        else:
            def predicate(x, y):
                return x > y
            
        winner = attacker if predicate(attacker_result.total, defender_result.total) else defender
        
        return (attacker_result, defender_result, winner)
    
    @staticmethod
    async def _collateral(
        ctx: commands.GuildContext, 
        *, 
        attacker: discord.Member, 
        defender: discord.Member,
        count: int = 1
    ):
        collateral_list: typing.List[discord.Member] = []
        fetched: typing.List[discord.Message] = [
            message async for message in ctx.channel.history(limit=200)
        ]
        
        potentials: typing.List[discord.Member] = list(
            set([msg.author for msg in fetched])  # type: ignore[misc]
        )
        
        potentials = [
            t
            for t in potentials
            if t.id != defender.id and t.id != ctx.author.id and not t.bot
        ]

        if len(potentials) > 0:
            collateral_list = random.choices(potentials, k=count)
            pass

        return collateral_list
    
    @staticmethod
    def _embed(
        *,
        type: KeyType,
        attacker: discord.Member,
        defender: discord.Member,
        attacker_roll: d20.RollResult,
        defender_roll: d20.RollResult,
        winner: discord.Member,
        outcome: typing.Union[str, None, discord.Role],
        victims: typing.List[discord.Member],
        expiration : datetime,
    ):
        verb : str
        color : discord.Color
        if type == "curse":
            verb = "cursed"
            color = discord.Color.light_grey()
            emoji = '☠️'

        if type == "nyame":
            verb = "nyamed"
            color = discord.Color.orange()
            emoji = '🐱'

        if type == "rolecolors":
            verb = "painted"
            color = discord.Color.fuchsia()
            emoji = '🎨'

        description = ""
        description += f"__Type__: {verb.capitalize()}\n"
        description += ("**" if winner.id == attacker.id else "") + f"__Attacker__: {attacker.mention} ({attacker.display_name})" + ("**\n" if winner.id == attacker.id else "\n")
        description += ("**" if winner.id == defender.id else "") + f"__Defender__: {defender.mention} ({defender.display_name})" + ("**\n" if winner.id == defender.id else "\n")

        
        embed = discord.Embed(
            title=f"{emoji} {attacker.display_name} vs. {defender.display_name} {emoji}",
            color=color,
            description=description
        )

        attacker_roll_field = attacker_roll.result
        
        if attacker_roll.crit == d20.CritType.FAIL:
            attacker_roll_field = f":skull: Oh no, something went wrong... :skull:\n" + attacker_roll_field
            pass
        elif attacker_roll.crit == d20.CritType.CRIT:
            attacker_roll_field = f":dart: Your curse feels extra potent! :dart:\n" + attacker_roll_field
            pass

        embed.add_field(
            name=f"{'🏆 ' if attacker.id == winner.id else ''}{attacker.display_name}: *{attacker_roll.total}*", 
            value=attacker_roll_field, 
            inline=False
        )

        defender_roll_field = defender_roll.result

        # if defender_roll.crit == d20.CritType.FAIL:
        #     pass
        if defender_roll.crit == d20.CritType.CRIT:
            defender_roll_field += f"\n:shield: {defender.mention} ({defender.display_name}) shielded against the blow"
            collateral_list = [member for member in victims if member.id != defender.id]

            if len(collateral_list) > 0:
                defender_roll_field += f"...and it ended up hitting another by mistake" 

            defender_roll_field += "!\n"

        embed.add_field(
            name=f"{'🏆 ' if defender.id == winner.id else ''}{defender.display_name}: *{defender_roll.total}*", 
            value=defender_roll_field, 
            inline=False
        )

        if len(victims) > 1:
            embed.add_field(
                name="Victims", 
                value='\n'.join(f"{victim.mention} ({discord.utils.escape_markdown(victim.display_name)})" for victim in victims), 
                inline=False
            )

        result_field = ""
        if type == "curse":
            result_field += f"__Curse Name__: {discord.utils.escape_markdown(outcome)}\n" # type: ignore[arg-type]
        if type == "nyame":
            pass
        if type == "rolecolors":
            result_field += f"__Color__: {outcome.mention}\n" # type: ignore[union-attr]

        if winner.id == attacker.id:
            result_field += f"__Until__: <t:{int(expiration.timestamp())}:R>"

        embed.add_field(name=" ", value=result_field, inline=False)

        if winner.id == attacker.id:
            embed.set_footer(text=f"✅ {attacker.display_name} succesfully {verb} {defender.display_name}!")
        else:
            embed.set_footer(text=f"❌ {attacker.display_name} failed to afflict {defender.display_name}!")

        return embed

    @commands.group()
    @commands.guild_only()
    async def battler(self, ctx: commands.GuildContext) -> None:
        """
        Battler commands.
        """
        pass

    @battler.command()
    @commands.guild_only()
    async def race(self, ctx: commands.GuildContext, race: typing.Annotated[Race, RaceConverter]) -> None:
        pass