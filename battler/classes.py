import typing
import discord
from redbot.core.config import Config
from redbot.core import commands

from .config import Equipment, KeyType, Modifier, Race

class BattleUser():
    equipment: typing.List[Equipment]
    race: Race
    member: discord.Member

    def __init__(
            self, 
            *,
            config: Config, 
            member: discord.Member
        ):
        self.guild_config = config.guild(member.guild)
        self.member_config = config.member(member)

    async def collect(self):
        equipment_ids = await self.member_config.equipment_ids()
        race_id = await self.member_config.race_id()

        guild_equipment : typing.List[Equipment] = await self.guild_config.equipment()
        guild_races : typing.List[Race] = await self.guild_config.races()

        self.equipment = [e for e in guild_equipment if e["id"] in equipment_ids]
        self.race = [r for r in guild_races if r['id'] == race_id][0]

        return self


def ApplyModifier(roll: str, modifier: Modifier):
    if modifier['operator'] == 'add':
        return f"{roll}+{modifier['value']}"
    if modifier['operator'] == 'multiply':
        return f"{roll}*{modifier['value']}"
    if modifier['operator'] == 'set':
        return f"{modifier['value']}"
    
    raise commands.BadArgument('Invalid modifier operator.')

def ApplyModifiers(roll: str, battle_user: BattleUser, battle_types: typing.Optional[typing.List[KeyType]]):
    for equipment in battle_user.equipment:
        for modifier in equipment['modifiers']:
            if battle_types is None or modifier['type'] in battle_types:
                roll = ApplyModifier(roll, modifier)
                
    for modifier in battle_user.race['modifiers']:
        if battle_types is None or modifier['type'] in battle_types:
            roll = ApplyModifier(roll, modifier)
    return roll