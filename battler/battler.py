from datetime import datetime
import random
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

import d20  # type: ignore[import-untyped]

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.core.converter import DogCogConverter
from dogscogs.converters.percent import Percent

from .embed import BattlerRaceEmbed, BattlerStatusEmbed
from .config import BattlerConfig, BattleUserConfig, KeyType, Race, Equipment
from .classes import BattleUser, applyModifiers
from .views.races import AdminRacePaginatedEmbed, SelectRacePaginatedEmbed
from .views.equipment import AdminEquipmentPaginatedEmbed, PurchaseEquipmentPaginatedEmbed

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD: BattlerConfig = {
    "attacker_wins_ties": True,
    "attacker_roll": "1d20",
    "defender_roll": "1d20",
    "sell_ratio": 0.5,
    "use_embed": False,
    "races": [
        {
            "id": 0,
            "name": "Human",
            "description": "Humans are boring.",
            "role_id": None,
            "image_url": "https://static.wikia.nocookie.net/touhou/images/c/c8/Th18Reimu.png/revision/latest?cb=20210321123419",
            "modifiers": [],
        },
    ],
    "equipment": [],
    "channel_ids": [],
}

DEFAULT_MEMBER: BattleUserConfig = {
    "equipment_ids": [],
    "race_id": None,
    "is_silent": False,
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

    if attacker.id == defender.id:
        results['footer'] = f"❓ {attacker.display_name} tried to {results['verb']} themselves"
    elif winner.id == attacker.id:
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

        attacker_roll = applyModifiers(attacker_roll, attacker_battle_user, battle_types, ['attack', 'both'])
        defender_roll = applyModifiers(defender_roll, defender_battle_user, battle_types, ['defend', 'both'])

        attacker_result = d20.roll(attacker_roll)

        if attacker.id == defender.id:
            defender_result = d20.roll('10')
        else:
            defender_result = d20.roll(defender_roll)

        if await config.guild(guild).attacker_wins_ties():
            def predicate(x, y):
                return x >= y
        else:
            def predicate(x, y):
                return x > y
            
        winner = attacker if predicate(attacker_result.total, defender_result.total) else defender

        if attacker_result.crit == d20.CritType.CRIT:
            winner = attacker
        if attacker_result.crit == d20.CritType.FAIL:
            winner = defender
        
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
    async def _send_battler_dm(user: discord.Member, *args, **kwargs) -> None:
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Battler",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        is_silent = await config.member(user).is_silent()

        if not is_silent:
            await user.send(*args, **kwargs)

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

    @battler.command()
    @commands.is_owner()
    @commands.guild_only()
    async def clear_all(self, ctx: commands.GuildContext) -> None:
        """Clear all battler data."""
        await self.config.guild(ctx.guild).clear()
        await ctx.reply("All battler data has been cleared for this server.")
        pass

    @battler.command()
    @commands.is_owner()
    @commands.guild_only()
    async def set(self, ctx: commands.GuildContext, member: discord.Member, key: str, *, value: str) -> None:
        """Set a value for a member."""
        parsed_value : typing.Union[int, typing.List[int]]

        key = key.lower()

        if key == 'race_id':
            try:
                parsed_value = int(value)
            except ValueError:
                raise commands.BadArgument("Value must be an integer.")
            
        elif key == 'equipment_ids':
            try:
                parsed_value = [int(v) for v in value.split(',')]
            except ValueError:
                raise commands.BadArgument("Value must be a list of integers.")
            
        else:
            raise commands.BadArgument(f"Key `{key}` not found.")

        await self.config.member(member).set_raw(key, value=parsed_value)
        await ctx.reply(f"Set `{key}` to `{value}` for {member.display_name}")
        pass

    @battler.command()
    @commands.is_owner()
    @commands.guild_only()
    async def clear(self, ctx: commands.GuildContext, member: discord.Member) -> None:
        """Clear a member's battler data."""
        await self.config.member(member).clear()
        await ctx.reply(f"Cleared battler data for {member.display_name}")
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
    async def embed(self, ctx: commands.GuildContext, use_embed: typing.Optional[bool] = None) -> None:
        """Toggle whether to use embeds for battle messages."""
        if use_embed is None:
            use_embed = not await self.config.guild(ctx.guild).use_embed()
        await self.config.guild(ctx.guild).use_embed.set(use_embed)
        await ctx.reply(f"Using {'`EMBEDS`' if use_embed else '`TEXT`'} for battle messages.")
        pass

    @battler_config.command()
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def buyback(self, ctx: commands.GuildContext, sell_ratio: typing.Optional[typing.Annotated[float, Percent]] = None) -> None:
        """Set the ratio at which equipment can be sold back."""
        if sell_ratio is None:
            sell_ratio = await self.config.guild(ctx.guild).sell_ratio()
        elif sell_ratio < 0 or sell_ratio > 1:
            raise commands.BadArgument("Sell ratio must be between 0 and 1.")

        await self.config.guild(ctx.guild).sell_ratio.set(sell_ratio)
        await ctx.reply(f"Equipment be sold back at a ratio of `{sell_ratio:%}`")
        pass

    @battler_config.command(aliases=['channel'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channels(self, ctx: commands.GuildContext, channels: commands.Greedy[discord.TextChannel]) -> None:
        """Set the channels where battle commands can be used."""
        channel_ids = [channel.id for channel in channels]
        await self.config.guild(ctx.guild).channel_ids.set(channel_ids)

        if len(channel_ids) == 0:
            await ctx.reply("Battler commands can now be used anywhere.")
        else:
            await ctx.reply(f"Battler commands now only be used in {', '.join([channel.mention for channel in channels])}")
        pass

    @battler_config.command(name='equipment')
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def config_equipment(self, ctx: commands.GuildContext) -> None:
        """Adjust the existing equipment that users can purchase."""
        await AdminEquipmentPaginatedEmbed(
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
        ).send()
        pass

    @battler_config.command(name='races', aliases=['race'])
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

    @battler.command()
    @commands.guild_only()
    async def mute(self, ctx: commands.GuildContext, is_muted: typing.Optional[bool] = None):
        """Mute or unmute your battler messages."""
        if is_muted is None:
            is_muted = await self.config.member(ctx.message.author).is_silent()

        await self.config.member(ctx.message.author).is_silent.set(is_muted)
        await ctx.reply(f"Battler messages sent to you via DM are {'`MUTED`' if is_muted else '`UNMUTED`'}")
        pass

    @battler.command(alises=["stats"])
    @commands.guild_only()
    async def info(self, ctx: commands.GuildContext, member: typing.Optional[discord.Member]) -> None:
        """Get your battler information."""
        channel_ids : typing.List[int] = await self.config.guild(ctx.guild).channel_ids()
        if len(channel_ids) > 0 and ctx.channel.id not in channel_ids:
            await ctx.reply("You can't use that command here.", delete_after=5)
            await ctx.message.delete(delay=5)
            return
        
        if member is None:
            member = ctx.guild.get_member(ctx.message.author.id) or await ctx.guild.fetch_member(ctx.message.author.id)

        embed = BattlerStatusEmbed(
            config=self.config,
            guild=ctx.guild,
            member=member,
        ).send()

        await ctx.reply(embed=await embed)
        pass

    @battler.command()
    @commands.guild_only()
    async def race(self, ctx: commands.GuildContext) -> None:
        """See or set your race (if you haven't done so already)."""
        channel_ids : typing.List[int] = await self.config.guild(ctx.guild).channel_ids()
        if len(channel_ids) > 0 and ctx.channel.id not in channel_ids:
            await ctx.reply("You can't use that command here.", delete_after=5)
            await ctx.message.delete(delay=5)
            return

        race_id = await self.config.member(ctx.message.author).race_id()

        if race_id is not None:
            races = await self.config.guild(ctx.guild).races()
            chosen_race = next((r for r in races if r['id'] == race_id), None)

            if chosen_race is not None:
                role = ctx.guild.get_role(chosen_race['role_id'])

                if role is not None and role not in ctx.message.author.roles: # type: ignore[union-attr]
                    await ctx.message.author.add_roles(role, reason="Battler Role") # type: ignore[union-attr]

                await ctx.reply(content=f"{ctx.message.author.mention}'s race is set to: {chosen_race['name']}",
                    embed=await BattlerRaceEmbed(
                    config=self.config,
                    guild=ctx.guild,
                    race_id=race_id,
                ).send())
                return
        
        await SelectRacePaginatedEmbed(
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
        ).send()

        pass

    @battler.command(aliases=["gear"])
    @commands.guild_only()
    async def equipment(self, ctx: commands.GuildContext, equipment: typing.Annotated[Equipment, EquipmentConverter]) -> None:
        """See your equipment list."""
        channel_ids : typing.List[int] = await self.config.guild(ctx.guild).channel_ids()
        if len(channel_ids) > 0 and ctx.channel.id not in channel_ids:
            await ctx.reply("You can't use that command here.", delete_after=5)
            await ctx.message.delete(delay=5)
            return
        
        await ctx.reply("Will be implemented later.", delete_after=5)
        
        pass

    @battler.command(aliases=["shop"])
    @commands.guild_only()
    async def purchase(self, ctx: commands.GuildContext):
        """Purchase equipment."""
        channel_ids : typing.List[int] = await self.config.guild(ctx.guild).channel_ids()
        if len(channel_ids) > 0 and ctx.channel.id not in channel_ids:
            await ctx.reply("You can't use that command here.", delete_after=5)
            await ctx.message.delete(delay=5)
            return
        
        await PurchaseEquipmentPaginatedEmbed(
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
        ).send()
        pass

    async def cog_load(self) -> None:
        guilds : typing.Dict[int, BattlerConfig] = await self.config.all_guilds()

        for id in guilds.keys():
            for i in range(len(guilds[id]["races"])):
                if 'role_id' not in guilds[id]['races'][i]:
                    guilds[id]['races'][i]['role_id'] = None
                    
            await self.config.guild_from_id(id).races.set(guilds[id]['races'])
