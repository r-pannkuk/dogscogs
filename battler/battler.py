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

from .config import BattlerConfig, BattleUserConfig, KeyType, Race, Equipment
from .classes import BattleUser, ApplyModifiers
from .embed import BattlerRaceEmbed
from .views import AdminRacePaginatedEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD: BattlerConfig = {
    "attacker_wins_ties": True,
    "attacker_roll": "1d20",
    "defender_roll": "1d20",
    "use_embed": False,
    "races": [
        {
            "id": 0,
            "name": "Human",
            "description": "Humans are boring.",
            "image_url": "https://static.wikia.nocookie.net/touhou/images/c/c8/Th18Reimu.png/revision/latest?cb=20210321123419",
            "modifiers": [],
        },
    ],
    "equipment": [],
}

DEFAULT_MEMBER: BattleUserConfig = {
    "equipment_ids": [],
    "race_id": 0,
}

class _BattleMessageParts(typing.TypedDict):
    verb: str
    color: discord.Color
    emoji: str
    attacker_roll: str
    attacker_effects: str
    defender_roll: str
    defender_effects: str
    curse_effect: str
    title: str
    footer: str
    until: str

class BattleMessageComponents(typing.TypedDict, total=False):
    embed: typing.Optional[discord.Embed]
    content: typing.Optional[str]

def generate_battle_message_parts(
        *,
        type: KeyType,
        attacker: discord.Member,
        defender: discord.Member,
        attacker_roll: d20.RollResult,
        defender_roll: d20.RollResult,
        winner: discord.Member,
        outcome: typing.Union[str, None, discord.Role],
        victims: typing.List[discord.Member],
        expiration : datetime
    ) -> _BattleMessageParts :

    results : _BattleMessageParts = {
        "verb": "",
        "color": discord.Color.default(),
        "emoji": "",
        "attacker_roll": "",
        "attacker_effects": "",
        "defender_roll": "",
        "defender_effects": "",
        "curse_effect": "",
        "title": "",
        "footer": "",
        "until": "",
    }
    
    if type == "curse":
        results['verb'] = "cursed"
        results['color'] = discord.Color.light_grey()
        results['emoji'] = '☠️'

    if type == "nyame":
        results['verb'] = "nyamed"
        results['color'] = discord.Color.orange()
        results['emoji'] = '🐱'

    if type == "rolecolors":
        results['verb'] = "painted"
        results['color'] = discord.Color.fuchsia()
        results['emoji'] = '🎨'

    results['attacker_roll'] = ("**" if winner.id == attacker.id else "") + f"{'🏆 ' if attacker.id == winner.id else ''}{attacker.mention}: {attacker_roll.result}" + ("**" if winner.id == attacker.id else '')
    results['attacker_effects'] = ""

    if attacker_roll.crit == d20.CritType.FAIL:
        results['attacker_effects'] += f":skull: Oh no, something went wrong... :skull:"
        pass
    elif attacker_roll.crit == d20.CritType.CRIT:
        results['attacker_effects'] += f":dart: Your curse feels extra potent! :dart:"
        pass

    results['defender_roll'] = ("**" if winner.id == defender.id else "") + f"{'🏆 ' if defender.id == winner.id else ''}{defender.mention}: {defender_roll.result}" + ("**" if winner.id == defender.id else "")
    results['defender_effects'] = ""

    # if defender_roll.crit == d20.CritType.FAIL:
    #     pass
    if defender_roll.crit == d20.CritType.CRIT:
        results['defender_effects'] += f":shield: {defender.mention} ({defender.display_name}) shielded against the blow"
        collateral_list = [member for member in victims if member.id != defender.id]

        if len(collateral_list) > 0:
            results['defender_effects'] += f"...and it ended up hitting {','.join(f'{victim.mention} ({discord.utils.escape_markdown(victim.display_name)})' for victim in victims)} by mistake" 

        results['defender_effects'] += "!"

    if type == "curse":
        results['curse_effect'] = f"{discord.utils.escape_markdown(outcome)}" # type: ignore[arg-type]
    if type == "nyame":
        pass
    if type == "rolecolors":
        results['curse_effect'] = f"{outcome.mention}" # type: ignore[union-attr]

    if winner.id == attacker.id:
        results['until'] = f"<t:{int(expiration.timestamp())}:R>"

    results['title'] = f"{results['emoji']} {attacker.display_name} vs. {defender.display_name} {results['emoji']}"

    if winner.id == attacker.id:
        results['footer'] = f"✅ {attacker.display_name} succesfully {results['verb']} {defender.display_name}"
    else:
        results['footer'] = f"❌ {attacker.display_name} failed to afflict {defender.display_name}"

    return results

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
        

class EquipmentConverter(DogCogConverter):
    @staticmethod
    async def parse(ctx: commands.GuildContext, argument: str) -> Equipment: #type: ignore[override]
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Battler",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        try:
            guild_equipment : typing.List[Equipment] = await config.guild(ctx.guild).equipment()
            return next(e for e in guild_equipment if e['name'].lower() == argument.lower())
        except StopIteration:
            raise commands.BadArgument(f"`{argument}` is not an Equipment found in {ctx.guild.name} Battler configuration.")

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
    def _battle_message(
        *,
        type: KeyType,
        attacker: discord.Member,
        defender: discord.Member,
        attacker_roll: d20.RollResult,
        defender_roll: d20.RollResult,
        winner: discord.Member,
        outcome: typing.Union[str, None, discord.Role],
        victims: typing.List[discord.Member],
        expiration: datetime
    ) -> BattleMessageComponents:
        parts = generate_battle_message_parts(
            type=type,
            attacker=attacker,
            defender=defender,
            attacker_roll=attacker_roll,
            defender_roll=defender_roll,
            winner=winner,
            outcome=outcome,
            victims=victims,
            expiration=expiration
        )

        message_content = ""

        message_content += parts['attacker_roll'] + ' vs. ' + parts['defender_roll'] + "\n"
        message_content += f"{parts['attacker_effects']}\n" if parts['attacker_effects'] != '' else ""
        message_content += f"{parts['defender_effects']}\n" if parts['defender_effects'] != '' else ""
        message_content += f"{parts['footer']}"

        if type == "curse":
            message_content += f" with `{parts['curse_effect']}`\n"
        if type == "nyame":
            if winner.id == attacker.id:
                message_content += f" with a new nyame\n"
        if type == "rolecolors":
            message_content += f" with {parts['curse_effect']}\n" 

        for victim in victims:
            message_content += f"{attacker.mention} {parts['verb']} {victim.display_name} to {outcome.mention if isinstance(outcome, discord.Role) else outcome} until <t:{int(expiration.timestamp())}:R>!"

        return { "content": message_content }

    @staticmethod
    def _battle_embed(
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
    ) -> BattleMessageComponents:
        parts = generate_battle_message_parts(
            type=type,
            attacker=attacker,
            defender=defender,
            attacker_roll=attacker_roll,
            defender_roll=defender_roll,
            winner=winner,
            outcome=outcome,
            victims=victims,
            expiration=expiration
        )

        description = ""
        # description += f"__Type__: {verb.capitalize()}\n"
        # description += ("**" if winner.id == attacker.id else "") + f"__Attacker__: {attacker.mention} ({attacker.display_name})" + ("**\n" if winner.id == attacker.id else "\n")
        # description += ("**" if winner.id == defender.id else "") + f"__Defender__: {defender.mention} ({defender.display_name})" + ("**\n" if winner.id == defender.id else "\n")

        # description += "\n"

        description += f"__Attacker__: {parts['attacker_roll']}\n"
        description += f"{parts['attacker_effects']}\n\n" if parts['attacker_effects'] != '' else ""
        description += f"__Defender__: {parts['defender_roll']}\n"
        description += f"{parts['defender_effects']}\n\n" if parts['defender_effects'] != '' else ""
        description += "\n"

        if type == "curse":
            description += f"__Curse Name__: `{parts['curse_effect']}`"
        if type == "nyame":
            if winner.id == attacker.id:
                description += f"__Victims__: {', '.join([victim.mention for victim in victims])}"
        if type == "rolecolors":
            description += f"__Color__: {parts['curse_effect']}" 

        if winner.id == attacker.id:
            description += f" until {parts['until']}"
            
        embed = discord.Embed(
            title=parts['title'],
            color=parts['color'],
            description=description
        )

        # embed.set_footer(text=parts['footer'])

        return { "embed": embed }

    @staticmethod
    async def _battle_response(
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
    ) -> BattleMessageComponents:
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Battler",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )

        guild = attacker.guild

        use_embed : bool = await config.guild(guild).use_embed()

        if use_embed:
            return Battler._battle_embed(
                type=type,
                attacker=attacker,
                defender=defender,
                attacker_roll=attacker_roll,
                defender_roll=defender_roll,
                winner=winner,
                outcome=outcome,
                victims=victims,
                expiration=expiration
            )
        else:
            return Battler._battle_message(
                type=type,
                attacker=attacker,
                defender=defender,
                attacker_roll=attacker_roll,
                defender_roll=defender_roll,
                winner=winner,
                outcome=outcome,
                victims=victims,
                expiration=expiration
            )

    @commands.group()
    @commands.guild_only()
    async def battler(self, ctx: commands.GuildContext) -> None:
        """
        Battler commands.

        *Dame daze...zen zen dame da...Beatorrriiiiccceeeeeee~*
        """
        pass

    @battler.group(name="config")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def battler_config(self, ctx: commands.GuildContext) -> None:
        """Set up battle configurations or adjust races and equipment."""
        pass

    @battler_config.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def settings(self, ctx: commands.GuildContext) -> None:
        """Control battle settings and configurations.
        """
        await ctx.reply("This doesn't do anything at the moment.")
        pass

    @battler_config.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def embed(self, ctx: commands.GuildContext, use_embed: typing.Optional[bool] = None) -> None:
        """Toggle whether to use embeds for battle messages."""
        if use_embed is None:
            use_embed = not await self.config.guild(ctx.guild).use_embed()
        await self.config.guild(ctx.guild).use_embed.set(use_embed)
        await ctx.reply(f"Using {'`EMBEDS`' if use_embed else '`TEXT`'} for battle messages.")
        pass

    @battler_config.command(name='equipment')
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def config_equipment(self, ctx: commands.GuildContext) -> None:
        """Adjust the existing equipment that users can purchase."""
        pass

    @battler_config.command(name='races')
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def config_races(self, ctx: commands.GuildContext) -> None:
        """Adjust what races players can choose from."""
        await AdminRacePaginatedEmbed(
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
        ).send()
        pass

    @battler.command(alises=["stats"])
    @commands.guild_only()
    async def info(self, ctx: commands.GuildContext, member: typing.Optional[discord.Member]) -> None:
        """Get your battler information."""
        pass

    @battler.command()
    @commands.guild_only()
    async def race(self, ctx: commands.GuildContext, race: typing.Annotated[Race, RaceConverter]) -> None:
        """See or set your race (if you haven't done so already)."""
        pass

    @battler.command(aliases=["gear"])
    @commands.guild_only()
    async def equipment(self, ctx: commands.GuildContext, equipment: typing.Annotated[Equipment, EquipmentConverter]) -> None:
        """See your equipment list."""
        pass

    @battler.command(aliases=["shop"])
    @commands.guild_only()
    async def purchase(self, ctx: commands.GuildContext):
        """Purchase equipment."""
        pass