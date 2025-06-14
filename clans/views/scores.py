import typing
import discord
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.bot import Red


from dogscogs.views.prompts import NumberPromptTextInput

from ..characters import Characters

from ..config import (
    ClanBattleRecord,
)
from ..embeds import BattleRecordEmbed

class BattleRecordDetailsModal(discord.ui.Modal):

    player1_games_won_field : NumberPromptTextInput = NumberPromptTextInput(
        required=False,
        custom_id="player1_games_won",
        label=" Games Won",
        min=0,
        max=999,
        style=discord.TextStyle.short,
        placeholder="0",
    )
    player2_games_won_field : NumberPromptTextInput = NumberPromptTextInput(
        required=False,
        custom_id="player2_games_won",
        label=" Games Won",
        min=0,
        max=999,
        style=discord.TextStyle.short,
        placeholder="0",
    )

    player1_games_won: int
    player2_games_won: int

    successful: bool = False

    def __init__(
        self,
        *args,
        player1: discord.Member,
        player2: discord.Member,
        player1_games : typing.Optional[int] = None,
        player2_games : typing.Optional[int] = None,
        title: str = "Battle Record Details",
        **argv,
    ):
        self.valid_members = [player1, player2]
        self.player1_games_won = player1_games
        self.player2_games_won = player2_games

        self.player1_games_won_field.label = f"{player1.display_name} Games Won"
        self.player2_games_won_field.label = f"{player2.display_name} Games Won"

        if player1_games:
            self.player1_games_won_field.default = player1_games
        if player2_games:
            self.player2_games_won_field.default = player2_games

        super().__init__(*args, title=title, timeout=60 * 10, **argv)
        pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not (
            interaction.user.guild_permissions.manage_roles or 
            interaction.user.id in [member.id for member in self.valid_members]
        ):
            raise ValueError("You are not allowed to interact with this message.")
        
        return (
            await self.player1_games_won_field.interaction_check(interaction) and 
            await self.player2_games_won_field.interaction_check(interaction)
        )

    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True, delete_after=10
        )
        pass

    async def on_submit(self, interaction: discord.Interaction):
        self.player1_games_won = self.player1_games_won_field.value
        self.player2_games_won = self.player2_games_won_field.value
        self.successful = True
        await interaction.response.defer()

class CreateBattleReportView(discord.ui.View):
    def __init__(
        self,
        bot: Red,
        config: Config,
        guild: discord.Guild,
        ctx: commands.GuildContext,
        message: discord.Message,
        author_id: int,
        battle_record_id: int,
    ):
        super().__init__(timeout=None)

        self.bot = bot
        self.config = config
        self.guild = guild
        self.ctx = ctx
        self.message = message
        self.author_id = author_id
        self.battle_record_id = battle_record_id

    async def collect(self) -> "CreateBattleReportView":
        self.clear_items()

        battle_record: ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )

        self.add_item(self.edit_stats)

        if battle_record['winner_id'] is not None:
            winner_registrant = await self.config.guild(self.guild).get_raw(
                "clan_registrants", battle_record['winner_id']
            )
            self.winner.default_values = [self.guild.get_member(winner_registrant['member_id'])]

        self.add_item(self.winner)

        self.player1_character.options = [
            discord.SelectOption(
                label=character["name"].capitalize(),
                default=key == battle_record['player1_character'],
                value=key,
            )
            for key, character in zip(Characters.keys(), Characters.values())
        ]

        self.player2_character.options = [
            discord.SelectOption(
                label=character["name"].capitalize(),
                default=key == battle_record['player2_character'],
                value=key,
            )
            for key, character in zip(Characters.keys(), Characters.values())
        ]

        self.add_item(self.player1_character)
        self.add_item(self.player2_character)
        self.add_item(self.submit)
        self.add_item(self.cancel)

        embed = BattleRecordEmbed(
            ctx=self.ctx,
            guild_config=await self.config.guild(self.guild).all(),
            battle_record_id=self.battle_record_id,
        )

        await self.message.edit(embed=embed, view=self)

        return self

    async def on_timeout(self):
        if self.message:
            try:
                await self.message.edit(view=None)
            except discord.NotFound:
                pass
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                pass

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user.guild_permissions.manage_roles:
            return True

        battle_record: ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )

        player1_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player1_registrant_id"]
        )
        player2_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player2_registrant_id"]
        )

        if interaction.user.id not in [
            player1_registrant["member_id"],
            player2_registrant["member_id"],
        ]:
            return False

        return True

    @discord.ui.button(
        label="Edit Stats",
        custom_id="edit_stats",
        style=discord.ButtonStyle.primary,
        row=0,
    )
    async def edit_stats(
        self, interaction: discord.Interaction, button: discord.Button
    ):
        """
        Edits the match information, such as the number of rounds.
        """
        battle_record : ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )
        player1_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player1_registrant_id"]
        )
        player2_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player2_registrant_id"]
        )

        modal = BattleRecordDetailsModal(
            title="Edit Battle Record Details",
            player1=self.guild.get_member(player1_registrant["member_id"]),
            player2=self.guild.get_member(player2_registrant["member_id"]),
            player1_games=battle_record["player1_games_won"],
            player2_games=battle_record["player2_games_won"],
        )

        await interaction.response.send_modal(modal)

        if await modal.wait() or not modal.successful:
            return
        
        if battle_record["player1_games_won"] != modal.player1_games_won or \
           battle_record["player2_games_won"] != modal.player2_games_won:
            battle_record["player1_verified"] = False
            battle_record["player2_verified"] = False
        
        battle_record["player1_games_won"] = modal.player1_games_won
        battle_record["player2_games_won"] = modal.player2_games_won

        if battle_record["player1_games_won"] > battle_record["player2_games_won"]:
            battle_record["winner_id"] = battle_record["player1_registrant_id"]
            self.submit.disabled = False
        elif battle_record["player2_games_won"] > battle_record["player1_games_won"]:
            battle_record["winner_id"] = battle_record["player2_registrant_id"]
            self.submit.disabled = False

        await self.config.guild(self.guild).set_raw(
            "clan_battle_records", self.battle_record_id, value=battle_record
        )

        await self.collect()
        pass

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        custom_id="winner",
        placeholder="Select the Winner",
        min_values=1,
        max_values=1,
    )
    async def winner(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ):
        """
        Selects the winner of the match.
        """
        await interaction.response.defer()

        battle_record: ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )
        player1_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player1_registrant_id"]
        )
        player2_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player2_registrant_id"]
        )
        player1_member = self.guild.get_member(player1_registrant["member_id"])
        player2_member = self.guild.get_member(player2_registrant["member_id"])

        if select.values[0].id == player1_registrant["member_id"]:
            battle_record["winner_id"] = player1_registrant["id"]
            battle_record["player1_verified"] = False
            battle_record["player2_verified"] = False
        elif select.values[0].id == player2_registrant["member_id"]:
            battle_record["winner_id"] = player2_registrant["id"]
            battle_record["player1_verified"] = False
            battle_record["player2_verified"] = False
        else:
            await interaction.followup.send(
                f"Winner must be one of the participants: {player1_member.mention} or {player2_member.mention}.", ephemeral=True,
            )
            return
        
        await self.config.guild(self.guild).set_raw(
            "clan_battle_records", self.battle_record_id, value=battle_record
        )

        self.submit.disabled = False
        
        await self.collect()

    @discord.ui.select(
        custom_id="player1_character",
        placeholder="Player 1's Character",
        max_values=1,
        options=[
            discord.SelectOption(
                label=character["name"].capitalize(),
                value=key,
            )
            for key, character in zip(Characters.keys(), Characters.values())
        ],
    )
    async def player1_character(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """
        Selects the character for player 1.
        """
        await interaction.response.defer()

        battle_record : ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )

        battle_record["player1_character"] = select.values[0]
        battle_record["player1_verified"] = False
        battle_record["player2_verified"] = False

        await self.config.guild(self.guild).set_raw(
            "clan_battle_records", self.battle_record_id, value=battle_record
        )

        await self.collect()
        pass

    @discord.ui.select(
        custom_id="player2_character",
        placeholder="Player 2's Character",
        max_values=1,
        options=[
            discord.SelectOption(
                label=character["name"].capitalize(),
                value=key,
            )
            for key, character in zip(Characters.keys(), Characters.values())
        ],
    )
    async def player2_character(
        self, interaction: discord.Interaction, select: discord.ui.Select
    ):
        """
        Selects the character for player 2.
        """
        await interaction.response.defer()

        battle_record : ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )

        battle_record["player2_character"] = select.values[0]
        battle_record["player1_verified"] = False
        battle_record["player2_verified"] = False

        await self.config.guild(self.guild).set_raw(
            "clan_battle_records", self.battle_record_id, value=battle_record
        )

        await self.collect()
        pass

    @discord.ui.button(
        label="Submit",
        custom_id="submit_record",
        style=discord.ButtonStyle.success,
        disabled=True,
        row=4,
    )
    async def submit(self, interaction: discord.Interaction, button: discord.Button):
        """
        Verifies and submits the record.
        """
        await interaction.response.defer()
        battle_record : ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )
        player1_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player1_registrant_id"]
        )
        player2_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player2_registrant_id"]
        )

        # Maybe add a check here to see if games won lines up with the winner

        if interaction.user.id == player1_registrant["member_id"]:
            battle_record["player1_verified"] = True
        elif interaction.user.id == player2_registrant["member_id"]:
            battle_record["player2_verified"] = True

        await self.config.guild(self.guild).set_raw(
            "clan_battle_records", self.battle_record_id, value=battle_record
        )
        
        if not (battle_record["player1_verified"] and battle_record["player2_verified"]):
            followup = await interaction.followup.send("Response has been recorded.  Awaiting both verifications.", ephemeral=True)
            await self.collect()
            await followup.delete(delay=10)
        else:
            self.submit.disabled = True
            self.cancel.disabled = True
            self.edit_stats.disabled = True
            self.winner.disabled = True
            self.player1_character.disabled = True
            self.player2_character.disabled = True

            followup : discord.Message = await interaction.followup.send("Both players have verified the record.  Submitting.")

            await self.collect()
            embed = BattleRecordEmbed(
                ctx=self.ctx,
                guild_config=await self.config.guild(self.guild).all(),
                battle_record_id=self.battle_record_id,
            )

            await self.message.edit(embed=embed, view=None)

            await followup.delete(delay=10)

    @discord.ui.button(
        label="Cancel",
        custom_id="cancel_record",
        style=discord.ButtonStyle.danger,
        disabled=False,
        row=4,
    )
    async def cancel(self, interaction: discord.Interaction, button: discord.Button):
        """
        Cancels verification of the record.
        """
        battle_record : ClanBattleRecord = await self.config.guild(self.guild).get_raw(
            "clan_battle_records", self.battle_record_id
        )
        player1_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player1_registrant_id"]
        )
        player2_registrant = await self.config.guild(self.guild).get_raw(
            "clan_registrants", battle_record["player2_registrant_id"]
        )

        if interaction.user.id == player1_registrant["member_id"]:
            battle_record["player1_verified"] = False
        elif interaction.user.id == player2_registrant["member_id"]:
            battle_record["player2_verified"] = False
        else:
            await self.config.guild(self.guild).clear_raw("clan_battle_records", self.battle_record_id)
            await interaction.response.send_message("Cancelled.", delete_after=10)
            return
        
        await self.config.guild(self.guild).set_raw(
            "clan_battle_records", self.battle_record_id, value=battle_record
        )
        
        await self.message.delete()
