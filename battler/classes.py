import typing
import discord
from redbot.core.config import Config
from redbot.core import commands

from .config import BonusType, Equipment, KeyType, Modifier, Race

class BattleUser():
    equipment: typing.List[Equipment]
    race: typing.Union[Race, None] = None
    member: discord.Member

    def __init__(
            self, 
            *,
            config: Config, 
            member: discord.Member
        ):
        self.guild_config = config.guild(member.guild)
        self.member_config = config.member(member)

    async def collect(self) -> 'BattleUser':
        equipment_ids = await self.member_config.equipment_ids()
        race_id = await self.member_config.race_id()

        guild_equipment : typing.List[Equipment] = await self.guild_config.equipment()
        guild_races : typing.List[Race] = await self.guild_config.races()

        self.equipment = [e for e in guild_equipment if e["id"] in equipment_ids]
        self.race = next((r for r in guild_races if r['id'] == race_id), None)

        return self


def applyModifier(roll: str, modifier: Modifier):
    if modifier['operator'] == 'add':
        return f"{roll}{modifier['value']:+}"
    if modifier['operator'] == 'multiply':
        return f"{roll}*({modifier['value']})"
    if modifier['operator'] == 'set':
        return f"{modifier['value']}"
    
    raise commands.BadArgument('Invalid modifier operator.')

def applyModifiers(roll: str, battle_user: BattleUser, curse_types: typing.Optional[typing.List[KeyType]], attack_type: typing.Optional[typing.List[BonusType]]):
    modifiers : typing.List[Modifier] = []

    for equipment in battle_user.equipment:
        for modifier in equipment['modifiers']:
            if (curse_types is None or modifier['key'] in curse_types) and (attack_type is None or modifier['type'] in attack_type):
                modifiers.append(modifier)
    
    if battle_user.race is not None:
        for modifier in battle_user.race['modifiers']:
            if (curse_types is None or modifier['key'] in curse_types) and (attack_type is None or modifier['type'] in attack_type):
                modifiers.append(modifier)

    modifiers.sort(key=lambda m: (
        0 if m['operator'] == 'set' else 1 if m['operator'] == 'multiply' else 2,  # Put all 'set' operators first 
        m['value']                              # Sort by value ascending, so highest set is last.
    ))

    for modifier in modifiers:
        roll = applyModifier(roll, modifier)

    return roll