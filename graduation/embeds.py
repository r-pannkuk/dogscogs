import typing
import discord
from redbot.core import commands

from .config import GuildConfig, RegisteredRole, get_registry_entry

class GraduationConfigEmbed(discord.Embed):
    guild_config : GuildConfig

    def __init__(self, *args, guild: discord.Guild, guild_config : GuildConfig, **kwargs):
        self.guild_config = guild_config
        self.guild = guild
        super().__init__(*args, **kwargs)

    async def ready(self):
        self.title = "Graduation Configuration"
        self.description = "This is the current configuration for the Graduation cog."

        head_id = self.guild_config['head_id']
        head = get_registry_entry(head_id, self.guild_config['registry'])
        depth = 0

        def print_role(head: RegisteredRole, registry: typing.List[RegisteredRole]):
            nonlocal depth
            role = discord.utils.get(self.guild.roles, id=head['role_id'])
            if role is None:
                return
            
            output = f"{role.mention}"

            depth += 1

            for next_id in head['next_ids']:
                registry_entry = get_registry_entry(next_id, registry)
                if registry_entry is not None:
                    output += '\n' + ('᲼᲼' * depth) + f"┗▸{print_role(registry_entry, registry)}"

            depth -= 1
            
            return output

        self.description = f"{print_role(head, self.guild_config['registry'])}"

        return self

    pass