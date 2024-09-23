import typing
import discord
from redbot.core.bot import Red
from redbot.core.config import Config

from .config import BattleUserConfig, Equipment, Modifier, Race

TOKEN_BONUS_TYPE = "$BONUS$"
TOKEN_MODIFIER_KEY = "$KEY$"

def get_modifier_strings(modifiers: typing.List[Modifier]):
    modifier_strings = []

    for modifier in modifiers:
        modifier_string: str
        if int(modifier['value']) == modifier['value']:
            modifier['value'] = int(modifier['value'])

        if modifier["operator"] == "set":
            modifier_string = (
                f"Set {TOKEN_MODIFIER_KEY} ({TOKEN_BONUS_TYPE}) to {modifier['value']}"
            )
        if modifier["operator"] == "add":
            modifier_string = (
                f"{modifier['value']:+} to {TOKEN_MODIFIER_KEY} ({TOKEN_BONUS_TYPE})"
            )
        if modifier["operator"] == "multiply":
            modifier_string = (
                f"x{modifier['value']} to {TOKEN_MODIFIER_KEY} ({TOKEN_BONUS_TYPE})"
            )

        if modifier["key"] == "rolecolors":
            modifier_string = modifier_string.replace(
                TOKEN_MODIFIER_KEY, "Color Curses"
            )
        if modifier["key"] == "nyame":
            modifier_string = modifier_string.replace(TOKEN_MODIFIER_KEY, "Nyaming")
        if modifier["key"] == "curse":
            modifier_string = modifier_string.replace(
                TOKEN_MODIFIER_KEY, "Nickname Curses"
            )

        if modifier["type"] == "attack":
            modifier_string = modifier_string.replace(TOKEN_BONUS_TYPE, "Attacking")
        if modifier["type"] == "defend":
            modifier_string = modifier_string.replace(TOKEN_BONUS_TYPE, "Defending")
        if modifier["type"] == "both":
            modifier_string = modifier_string.replace(
                TOKEN_BONUS_TYPE, "Attacking and Defending"
            )

        modifier_strings.append(modifier_string)

    return modifier_strings

class BattlerRaceEmbed(discord.Embed):
    race_id: int
    config: Config
    guild: discord.Guild

    def __init__(self, config: Config, guild: discord.Guild, race_id: int):
        self.guild = guild
        self.config = config
        self.race_id = race_id

        super().__init__(title="Generating...")

    async def send(self, show_stats: bool = False) -> "BattlerRaceEmbed":
        races: typing.List[Race] = await self.config.guild(self.guild).races()
        race = next((r for r in races if r["id"] == self.race_id), None)

        if race is None:
            raise ValueError(f"No race found for the given id: {self.race_id}")

        self.title = race["name"]
        self.description = race["description"]

        modifier_strings = [
            f"- {string}" for string in get_modifier_strings(race["modifiers"])
        ]

        if len(modifier_strings) == 0:
            modifier_strings = ["- None"]

        self.add_field(
            name="Modifiers", value="\n".join(modifier_strings), inline=False
        )

        if show_stats:
            stats_string = ""

            count = 0

            all_members: typing.Dict[int, BattleUserConfig] = (
                await self.config.all_members(self.guild)
            )
            filtered_members = [
                id
                for id, member_data in all_members.items()
                if member_data["race_id"] == self.race_id
            ]
            count = len(filtered_members)

            stats_string += f"__Users:__ {count}"

            if count > 0:
                stats_string += f": {', '.join([str((self.guild.get_member(id) or await self.guild.fetch_member(id)).mention or id) for id in filtered_members])}"

            self.add_field(name="Stats", value=stats_string, inline=False)

        if race['role_id'] is not None:
            role = self.guild.get_role(race['role_id'])
            if role is not None:
                self.add_field(name=" ", value=f"__Role__: {role.mention}", inline=True)

        self.set_thumbnail(url=race["image_url"])

        self.set_footer(text=f"ID: {race['id']}")

        return self

class BattlerEquipmentEmbed(discord.Embed):
    equipment_id: int
    config: Config
    guild: discord.Guild

    def __init__(self, config: Config, guild: discord.Guild, equipment_id: int):
        self.guild = guild
        self.config = config
        self.equipment_id = equipment_id

        super().__init__(title="Generating...")

    async def send(self, show_stats: bool = False) -> "BattlerEquipmentEmbed":
        guild_equipment : typing.List[Equipment] = await self.config.guild(self.guild).equipment()
        equipment = next((e for e in guild_equipment if e["id"] == self.equipment_id), None)

        if equipment is None:
            raise ValueError(f"No equipment found for the given id: {self.equipment_id}")

        self.title = equipment["name"]
        self.description = equipment["description"]

        equipment_string = ""
        equipment_string += f"__Slot:__ {equipment['slot'].capitalize()}\n"
        equipment_string += f"__Cost:__ {equipment['cost']}"

        self.add_field(name=" ", value=equipment_string, inline=True)

        modifier_strings = [
            f"- {string}" for string in get_modifier_strings(equipment["modifiers"])
        ]

        if len(modifier_strings) == 0:
            modifier_strings = ["- None"]

        self.add_field(
            name="Modifiers", value="\n".join(modifier_strings), inline=False
        )

        if show_stats:
            stats_string = ""

            count = 0

            all_members: typing.Dict[int, BattleUserConfig] = (
                await self.config.all_members(self.guild)
            )
            filtered_members = [
                id
                for id, member_data in all_members.items()
                if any(id == self.equipment_id for id in member_data["equipment_ids"])
            ]
            count = len(filtered_members)

            stats_string += f"__Users:__ {count}"

            if count > 0:
                stats_string += f": {', '.join([str((self.guild.get_member(id) or await self.guild.fetch_member(id)).mention or id) for id in filtered_members])}"

            self.add_field(name="Stats", value=stats_string, inline=False)

        self.set_thumbnail(url=equipment["image_url"])

        self.set_footer(text=f"ID: {equipment['id']}")

        return self


class BattlerStatusEmbed(discord.Embed):
    def __init__(self, battler: BattleUserConfig):
        pass


class BattlerConfigEmbed(discord.Embed):
    def __init__(self, client: Red, config: Config, guild: discord.Guild):
        super().__init__(
            title=f"{guild.name} Battler Configuration", color=discord.Color.green()
        )
        self.config = config
        self.client = client
        self.guild = guild
        self.group = config.guild(guild)

    async def collect(self):
        pass
