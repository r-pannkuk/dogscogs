import asyncio
from typing import Literal
import typing

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

CHUNK_SIZE = 100

# https://github.com/Rapptz/discord.py/blob/master/examples/views/confirm.py
# Define a simple View that gives us a confirmation menu
class Confirm(discord.ui.View):
    def __init__(self):
        super().__init__()
        self.value = None
        self.response : discord.Message = None

    # When the confirm button is pressed, set the inner value to `True` and
    # stop the View from listening to more input.
    # We also send the user an ephemeral message that we're confirming their choice.
    @discord.ui.button(label='Confirm', style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Confirming', ephemeral=True)
        self.response = interaction.message
        self.value = True
        self.stop()

    # This one is similar to the confirmation button except sets the inner value to `False`
    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message('Cancelling', ephemeral=True)
        self.response = interaction.message
        self.value = False
        self.stop()


class Purge(commands.Cog):
    """
    Purges X posts from a selected channel.
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(
            self,
            identifier=260288776360820736,
            force_registration=True,
        )
        pass

    @commands.hybrid_command()
    @commands.admin_or_can_manage_channel()
    async def purge(self, ctx: commands.Context, number: int, channel: typing.Optional[discord.TextChannel]):
        """Deletes up to X messages from the supplied channel (or current channel if none exists).

        Args:
            ctx (commands.Context): Command context.
            number (int): The number of posts to delete.
            channel (typing.Optional[discord.TextChannel]): The channel to delete from.  Defaults to current channel.
        """
        if channel is None:
            channel = ctx.channel

        messages = channel.history(limit=number, before=ctx.message, oldest_first=False)

        list = []

        async for message in messages:
            list.append(message)

        list.reverse()

        first_deleted_message : discord.Message = list[0]
        last_deleted_message : discord.Message = list [-1]

        number = len(list)

        embed = discord.Embed()
        embed.title = f"Deleting {number} message{'' if number == 1 else 's'}:"
        embed.description = f"Channel: {channel.mention}"
        embed.description += "\n"
        embed.description += f"First Message: {first_deleted_message.jump_url}"
        embed.description += "\n"
        embed.description += f"Last Message: {last_deleted_message.jump_url}"

        view = Confirm()

        await ctx.send(embed=embed, view=view)

        await view.wait()

        if view.value is None:
            await ctx.send("Timed out")
            pass
        elif view.value:
            # for i in range(0, len(list), CHUNK_SIZE):
            #     chunk = list[i: i + CHUNK_SIZE]
            await channel.purge(limit=number, before=ctx.message, bulk=True, oldest_first=False)
                # await view.response.edit(content=f"{i + CHUNK_SIZE if i + CHUNK_SIZE < number else number} out of {number} deleted.")
                # await asyncio.sleep(3)
            
            await ctx.send("Deleted.")
            pass
        else:
            await ctx.send(f"Cancelled.")
            pass

        
        pass
