import discord
from redbot.core import commands

class CancelPurgeView(discord.ui.View):
    author_id : int
    canceled: bool = False

    def __init__(self, ctx: commands.Context):
        super().__init__(timeout=None)
        self.author_id = ctx.author.id

    async def interaction_check(self, interaction: discord.Interaction[discord.Client]) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("You are not allowed to interact with this view.", ephemeral=True, delete_after=5)
            return False
        
        return await super().interaction_check(interaction)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger)  # type: ignore[arg-type]
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        self.canceled = True

        await interaction.response.send_message("Purge interrupted. May take some time to resolve.", ephemeral=True, delete_after=15)

        button.disabled = True
        await interaction.message.edit(view=self) # type: ignore[union-attr]