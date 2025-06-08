import datetime
import typing
import uuid
import discord
from redbot.core import commands
from redbot.core.config import Config
from redbot.core.bot import Red

from dogscogs.constants.discord.emoji import (
    MAX_NAME_LENGTH as EMOJI_MAX_NAME_LENGTH,
    MIN_NAME_LENGTH as EMOJI_MIN_NAME_LENGTH,
)
from dogscogs.constants.regex import (
    EMOJI_NAME as REGEX_EMOJI_NAME,
    EMOJI_URL as REGEX_EMOJI_URL,
)
from dogscogs.views.prompts import ValidImageURLTextInput, NumberPromptTextInput

from .characters import Characters

from .config import (
    GuildConfig,
    ChannelConfig,
    MemberConfig,
    ClanBattleRecord,
    ClanPointAward,
    ClanRegistrationConfig,
    ClanConfig,
    PendingClanConfigDraft,
    PendingClanRegistrationConfigDraft,
    get_active_clan,
    get_active_clan_registrant,
    get_all_clan_registrants,
    get_active_clan_registrant,
)
from .embeds import BattleRecordEmbed, ClanDraftEmbed

MAX_CLAN_MEMBERS = 4


class ClanDetailsModal(discord.ui.Modal):
    name_field: discord.ui.TextInput = discord.ui.TextInput(
        required=True,
        custom_id="clan_name",
        label="Name",
        max_length=30,
        min_length=2,
        style=discord.TextStyle.short,
        placeholder="ClanName",
    )
    description_field: discord.ui.TextInput = discord.ui.TextInput(
        required=False,
        custom_id="clan_description",
        label="Description",
        style=discord.TextStyle.paragraph,
        placeholder="A description of the clan.",
    )
    icon_field: ValidImageURLTextInput = ValidImageURLTextInput(
        required=False,
        custom_id="clan_icon",
        label="Icon URL",
        style=discord.TextStyle.paragraph,
        placeholder="https://example.com/clan_icon.png",
    )

    name: str
    description: str
    icon_url: str

    successful: bool = False

    def __init__(
        self,
        *args,
        author: discord.User,
        title: str = "New Clan",
        name_default: typing.Optional[str] = None,
        description_default: typing.Optional[str] = None,
        icon_default: typing.Optional[str] = None,
        **argv,
    ):
        if name_default:
            self.name_field.default = name_default

        if description_default:
            self.description_field.default = description_default

        if icon_default:
            self.icon_field.default = icon_default

        self.author = author

        super().__init__(*args, title=title, timeout=60 * 10, **argv)
        pass

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.icon_field.value != "" and self.icon_field.value is not None:
            if not await self.icon_field.interaction_check(interaction):
                raise ValueError("Invalid icon URL.")

        if interaction.user != self.author:
            raise ValueError("You are not allowed to interact with this message.")

        if not self.name_field.value:
            raise ValueError("Name is required.")

        return True

    async def on_error(self, interaction: discord.Interaction, error):
        await interaction.response.send_message(
            f"An error occurred: {error}", ephemeral=True, delete_after=10
        )
        pass

    async def on_submit(self, interaction: discord.Interaction):
        self.name = self.name_field.value
        self.description = self.description_field.value
        self.icon_url = self.icon_field.value
        self.successful = True
        await interaction.response.defer()


class EditClanDraftView(discord.ui.View):
    def __init__(
        self,
        bot: Red,
        config: Config,
        guild: discord.Guild,
        ctx: commands.GuildContext,
        message: discord.Message,
        author_id: int,
        clan_config: ClanConfig,
    ):
        super().__init__()

        self.bot = bot
        self.config = config
        self.guild = guild
        self.ctx = ctx
        self.message = message
        self.author_id = author_id
        self.clan_draft: PendingClanConfigDraft = clan_config.copy()
        self.clan_registrant_drafts: typing.Dict[
            str, PendingClanRegistrationConfigDraft
        ] = {}
        self.pending: bool = False

    async def collect(self) -> "EditClanDraftView":
        self.clear_items()

        guild_config: GuildConfig = await self.config.guild(self.guild).all()

        self.clan_draft["active_registrant_ids"] = list(
            set(self.clan_draft["active_registrant_ids"])
        )

        # If clan registrants aren't populated, grabbing the pre-existing list and adding them to the draft.
        for registrant_id in self.clan_draft["active_registrant_ids"]:
            if registrant_id not in self.clan_registrant_drafts:
                if registrant_id in guild_config["pending_clan_registrant_edits"]:
                    self.clan_registrant_drafts[registrant_id] = guild_config[
                        "pending_clan_registrant_edits"
                    ][registrant_id]
                elif registrant_id in guild_config["clan_registrants"]:
                    self.clan_registrant_drafts[registrant_id] = guild_config[
                        "clan_registrants"
                    ][registrant_id]
                else:
                    await self.bot.send_to_owners(
                        f"Registrant ID {registrant_id} not found in guild config for {self.guild.name}."
                    )

        if self.clan_draft["leader_registrant_id"] not in self.clan_registrant_drafts:
            if (
                self.clan_draft["leader_registrant_id"]
                in guild_config["pending_clan_registrant_edits"]
            ):
                self.clan_registrant_drafts[self.clan_draft["leader_registrant_id"]] = (
                    guild_config["pending_clan_registrant_edits"][
                        self.clan_draft["leader_registrant_id"]
                    ]
                )
            elif (
                self.clan_draft["leader_registrant_id"]
                in guild_config["clan_registrants"]
            ):
                self.clan_registrant_drafts[self.clan_draft["leader_registrant_id"]] = (
                    guild_config["clan_registrants"][
                        self.clan_draft["leader_registrant_id"]
                    ]
                )
            else:
                await self.bot.send_to_owners(
                    f"Leader registrant ID {self.clan_draft['leader_registrant_id']} not found in guild config for {self.guild.name}."
                )

        leader_registrant = self.clan_registrant_drafts[
            str(self.clan_draft["leader_registrant_id"])
        ]
        leader_member = self.guild.get_member(leader_registrant["member_id"])

        member_registrants: typing.List[ClanRegistrationConfig] = [
            self.clan_registrant_drafts[reg_id]
            for reg_id in self.clan_draft["active_registrant_ids"]
            if reg_id != leader_registrant["id"]
        ]
        members: typing.List[discord.Member] = [
            self.guild.get_member(reg["member_id"]) for reg in member_registrants
        ]

        self.toggle_active.label = (
            "Set Active" if not self.clan_draft["is_active"] else "Set Inactive"
        )
        self.toggle_active.style = (
            discord.ButtonStyle.success if not self.clan_draft["is_active"] else discord.ButtonStyle.danger
        )
        self.select_leader.default_values = [leader_member]
        self.select_members.default_values = list(set(members))

        self.add_item(self.toggle_active)
        self.add_item(self.edit_details)
        self.add_item(self.select_leader)
        self.add_item(self.select_members)

        if self.pending:
            self.add_item(self.save_draft)
            self.add_item(self.cancel_draft)

        embed = ClanDraftEmbed(
            guild=self.guild,
            clan_config=self.clan_draft,
            registrants=self.clan_registrant_drafts,
        )

        await self.message.edit(embed=embed, view=self)

        return self

    async def interaction_check(self, interaction: discord.Interaction):
        actual_config: ClanConfig = await self.config.guild(self.guild).get_raw(
            "clans", self.clan_draft["id"]
        )
        actual_registrant: ClanRegistrationConfig = await self.config.guild(
            self.guild
        ).get_raw("clan_registrants", actual_config["leader_registrant_id"])

        if (
            not interaction.user.guild_permissions.manage_roles
            and interaction.user.id != actual_registrant["member_id"]
        ):
            await interaction.response.send_message(
                "You do not have permission to interact with this message.",
                ephemeral=True,
                delete_after=10,
            )
            return False

        return await super().interaction_check(interaction)

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

    @discord.ui.button(label="Set Inactive", style=discord.ButtonStyle.danger)
    async def toggle_active(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.clan_draft["is_active"] = not self.clan_draft["is_active"]
        self.pending = True

        if self.clan_draft["is_active"]:
            self.clan_draft["active_registrant_ids"] = list(
                set(
                    self.clan_draft["active_registrant_ids"]
                    + [self.clan_draft["leader_registrant_id"]]
                )
            )

        await interaction.response.defer()

        await self.collect()
        pass

    @discord.ui.button(label="Edit Details", style=discord.ButtonStyle.primary)
    async def edit_details(
        self, interaction: discord.Interaction, _button: discord.ui.Button
    ):
        modal = ClanDetailsModal(
            title="Edit Clan Details",
            author=interaction.user,
            name_default=self.clan_draft["name"] if self.clan_draft else None,
            description_default=self.clan_draft["description"]
            if self.clan_draft
            else None,
            icon_default=self.clan_draft["icon_url"] if self.clan_draft else None,
        )

        await interaction.response.send_modal(modal)

        if await modal.wait() or not modal.successful:
            return

        if modal.name != self.clan_draft["name"]:
            self.clan_draft["name"] = modal.name
            self.pending = True

        if modal.description != self.clan_draft["description"]:
            self.clan_draft["description"] = modal.description
            self.pending = True

        if modal.icon_url != self.clan_draft["icon_url"]:
            self.clan_draft["icon_url"] = modal.icon_url
            self.pending = True

        await self.collect()
        pass

    # @discord.ui.button(custom_id="refresh", emoji="🔄", style=discord.ButtonStyle.green)
    # async def refresh(
    #     self, interaction: discord.Interaction, _button: discord.ui.Button
    # ):
    #     await interaction.response.defer()
    #     await self.collect()
    #     pass

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        custom_id="select_leader",
        placeholder="Select Leader",
        min_values=1,
        max_values=1,
    )
    async def select_leader(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ):
        await interaction.response.defer()

        member: discord.Member = select.values[0]

        clan_registrant = get_active_clan_registrant(
            await self.config.guild(self.guild).all(),
            await self.config.member(member).all(),
        )

        if (
            clan_registrant is None
            or clan_registrant["clan_id"] != self.clan_draft["id"]
        ):
            if len(self.clan_draft['active_registrant_ids']) > MAX_CLAN_MEMBERS:
                await interaction.followup.send(
                    "Cannot select a new member, as the clan already has the maximum number of members.",
                    ephemeral=True,
                )
                await self.message.edit(view=None)
                await self.collect()
                return
            
            possible_registrants = get_all_clan_registrants(
                await self.config.guild(self.guild).all(),
                await self.config.member(member).all(),
            )
            clan_registrant = next(
                (
                    reg
                    for reg in possible_registrants
                    if reg["clan_id"] == self.clan_draft["id"]
                ),
                None,
            )

            if clan_registrant is None:
                clan_registrant = next(
                    (
                        reg
                        for reg in self.clan_registrant_drafts.values()
                        if reg["member_id"] == member.id
                    ),
                    PendingClanRegistrationConfigDraft(
                        {
                            "id": str(uuid.uuid4().int),
                            "member_id": member.id,
                            "clan_id": self.clan_draft["id"],
                            "created_at": datetime.datetime.now().timestamp(),
                            "last_joined_at": datetime.datetime.now().timestamp(),
                            "draft_created_at": datetime.datetime.now().timestamp(),
                            "channel_id": None,
                            "message_id": None,
                        }
                    ),
                )

            self.clan_registrant_drafts[clan_registrant["id"]] = clan_registrant
            self.pending = True

        if self.clan_draft["leader_registrant_id"] != clan_registrant["id"]:
            self.clan_draft["leader_registrant_id"] = clan_registrant["id"]
            self.clan_draft["active_registrant_ids"] = list(
                set(self.clan_draft["active_registrant_ids"] + [clan_registrant["id"]])
            )
            self.pending = True

        await self.collect()

        return

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        custom_id="select_members",
        placeholder="Select Members",
        min_values=0,
        max_values=MAX_CLAN_MEMBERS,
    )
    async def select_members(
        self, interaction: discord.Interaction, select: discord.ui.UserSelect
    ):
        await interaction.response.defer()

        members = select.values

        for i, member in enumerate(members):
            clan_registrant = get_active_clan_registrant(
                await self.config.guild(self.guild).all(),
                await self.config.member(members[i]).all(),
            )

            if (
                clan_registrant is None
                or clan_registrant["clan_id"] != self.clan_draft["id"]
            ):
                possible_registrants = get_all_clan_registrants(
                    await self.config.guild(self.guild).all(),
                    await self.config.member(member).all(),
                )
                clan_registrant = next(
                    (
                        reg
                        for reg in possible_registrants
                        if reg["clan_id"] == self.clan_draft["id"]
                    ),
                    None,
                )
                if clan_registrant is None:
                    clan_registrant = next(
                        (
                            reg
                            for reg in self.clan_registrant_drafts.values()
                            if reg["member_id"] == member.id
                        ),
                        PendingClanRegistrationConfigDraft(
                            {
                                "id": str(uuid.uuid4().int),
                                "member_id": member.id,
                                "clan_id": self.clan_draft["id"],
                                "created_at": datetime.datetime.now().timestamp(),
                                "last_joined_at": datetime.datetime.now().timestamp(),
                                "draft_created_at": datetime.datetime.now().timestamp(),
                                "channel_id": None,
                                "message_id": None,
                            }
                        ),
                    )

                self.clan_registrant_drafts[clan_registrant["id"]] = clan_registrant
                self.pending = True

            if clan_registrant["id"] not in self.clan_draft["active_registrant_ids"]:
                self.clan_draft["active_registrant_ids"].append(clan_registrant["id"])
                clan_registrant["last_joined_at"] = datetime.datetime.now().timestamp()
                self.clan_registrant_drafts[clan_registrant["id"]] = clan_registrant
                self.pending = True

        removed_members = [
            reg
            for reg in self.clan_registrant_drafts.values()
            if reg["member_id"] not in [member.id for member in members]
            and reg["id"] != self.clan_draft["leader_registrant_id"]
        ]

        for removed_member in removed_members:
            self.clan_draft["active_registrant_ids"].remove(removed_member["id"])
            if removed_member["id"] in self.clan_registrant_drafts:
                self.clan_registrant_drafts.pop(removed_member["id"])
            self.pending = True

        await self.collect()

        return

    @discord.ui.button(label="Save Draft", style=discord.ButtonStyle.success, row=4)
    async def save_draft(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        await self.message.edit(view=None)

        channel_settings: ChannelConfig = await self.config.guild(self.guild).channels()

        if "EDIT" in channel_settings:
            draft_message_channel_id = channel_settings["EDIT"]
        else:
            draft_message_channel_id = self.message.channel.id

        draft_message_channel = self.guild.get_channel(draft_message_channel_id)

        draft_message = await draft_message_channel.send("SENDING")

        # Delete all other pending clan edits and messages
        pending_clan_edits: typing.Dict[str, PendingClanConfigDraft] = (
            await self.config.guild(self.guild).get_raw("pending_clan_edits")
        )
        for clan_id, pending_clan in pending_clan_edits.items():
            if clan_id == self.clan_draft["id"]:
                pending_message = self.guild.get_channel(
                    pending_clan["channel_id"]
                ).get_partial_message(pending_clan["message_id"])

                if pending_message and not pending_message.id == draft_message.id:
                    try:
                        await pending_message.delete()
                    except discord.NotFound:
                        pass

        # Saving clan draft
        self.clan_draft["message_id"] = draft_message.id
        self.clan_draft["channel_id"] = draft_message_channel.id
        self.clan_draft["draft_created_at"] = datetime.datetime.now().timestamp()

        await self.config.guild(self.guild).set_raw(
            "pending_clan_edits", self.clan_draft["id"], value=self.clan_draft
        )

        # Saving registrant drafts
        for registrant_id, registrant in self.clan_registrant_drafts.items():
            registrant["message_id"] = draft_message.id
            registrant["channel_id"] = draft_message_channel.id
            registrant["draft_created_at"] = datetime.datetime.now().timestamp()
            await self.config.guild(self.guild).set_raw(
                "pending_clan_registrant_edits", registrant_id, value=registrant
            )
            
        await ClanApprovalMessage(
            guild=self.guild,
            config=self.config,
            bot=self.bot,
            message=draft_message,
            clan_draft=self.clan_draft,
            registrant_drafts=self.clan_registrant_drafts,
        ).collect()

        self.pending = False

        await self.collect()

        await self.message.edit(
            content=f"Draft saved. See: {draft_message.jump_url}", view=None, embed=None
        )

        return

    @discord.ui.button(label="Cancel Draft", style=discord.ButtonStyle.danger, row=4)
    async def cancel_draft(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.clan_draft = await self.config.guild(self.guild).get_raw(
            "clans", self.clan_draft["id"]
        )
        self.clan_registrant_drafts = {}
        self.pending = False

        await interaction.response.send_message(
            "Draft cancelled.", ephemeral=True, delete_after=10
        )

        await self.collect()

        return


class ApproveClanDraftView(discord.ui.View):
    def __init__(
        self,
        bot: Red,
        config: Config,
        guild: discord.Guild,
        message: discord.Message,
        clan_config: PendingClanConfigDraft,
        clan_registrant_drafts: typing.Dict[str, PendingClanRegistrationConfigDraft],
    ):
        super().__init__(timeout=None)

        self.bot = bot
        self.config = config
        self.guild = guild
        self.message = message
        self.clan_config = clan_config
        self.clan_registrant_drafts = clan_registrant_drafts

    async def collect(self) -> "ApproveClanDraftView":
        self.clear_items()

        self.add_item(self.approve)
        self.add_item(self.reject)

        embed = ClanDraftEmbed(
            guild=self.guild,
            clan_config=self.clan_config,
            registrants=self.clan_registrant_drafts,
        )

        await self.message.edit(embed=embed, view=self)

        return self

    @discord.ui.button(label="Approve", style=discord.ButtonStyle.success)
    async def approve(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.defer()

        await self.message.edit(view=None)

        old_clan : ClanConfig = await self.config.guild(self.guild).get_raw(
            "clans", self.clan_config["id"]
        )

        await self.config.guild(self.guild).set_raw(
            "clans", self.clan_config["id"], value=self.clan_config
        )
        await self.config.guild(self.guild).set_raw(
            "clan_registrants",
            self.clan_config["leader_registrant_id"],
            value=self.clan_registrant_drafts[self.clan_config["leader_registrant_id"]],
        )

        for registrant_id, registrant in self.clan_registrant_drafts.items():
            await self.config.guild(self.guild).set_raw(
                "clan_registrants", registrant_id, value=registrant
            )
            member = self.guild.get_member(registrant["member_id"])
            existing_ids: typing.List[str] = await self.config.member(
                member
            ).clan_registrant_ids()
            existing_ids.append(registrant_id)
            await self.config.member(member).clan_registrant_ids.set(
                list(set(existing_ids))
            )

        await self.config.guild(self.guild).clear_raw(
            "pending_clan_edits", self.clan_config["id"]
        )
        # await self.config.guild(self.guild).clear_raw("pending_clan_registrant_edits", self.clan_config["leader_registrant_id"])

        for registrant_id, _ in self.clan_registrant_drafts.items():
            await self.config.guild(self.guild).clear_raw(
                "pending_clan_registrant_edits", registrant_id
            )

        updated_guild: GuildConfig = await self.config.guild(self.guild).all()

        inactive_registrants: typing.List[ClanRegistrationConfig] = []

        for registrant_id in self.clan_config["active_registrant_ids"]:
            registrant = updated_guild["clan_registrants"][registrant_id]
            all_registrants = get_all_clan_registrants(
                updated_guild,
                await self.config.member(
                    self.guild.get_member(registrant["member_id"])
                ).all(),
            )
            inactive_registrants.extend(
                [
                    reg
                    for reg in all_registrants
                    if reg["clan_id"] != self.clan_config["id"]
                ]
            )

        for clan in updated_guild["clans"].values():
            if clan["id"] != self.clan_config["id"]:
                clan["active_registrant_ids"] = list(
                    set(
                        [
                            reg_id
                            for reg_id in clan["active_registrant_ids"]
                            if reg_id not in [reg["id"] for reg in inactive_registrants]
                        ]
                    )
                )

                if clan["leader_registrant_id"] in [
                    reg["id"] for reg in inactive_registrants
                ]:
                    clan["is_active"] = False

                await self.config.guild(self.guild).set_raw(
                    "clans", clan["id"], value=clan
                )

        if updated_guild["channels"].get("EDIT_LOGS"):
            edit_log_channel = self.guild.get_channel(
                updated_guild["channels"]["EDIT_LOGS"]
            )
            if edit_log_channel:
                embed = ClanDraftEmbed(
                    guild=self.guild,
                    clan_config=self.clan_config,
                    registrants=self.clan_registrant_drafts,
                )
                await edit_log_channel.send(
                    f"Clan change approved by {interaction.user.mention}: {self.message.jump_url}.\n\n{interaction.message.content}",
                    embed=embed,
                    allowed_mentions= discord.AllowedMentions.none()
                )
        
        leader_role_id = updated_guild["roles"].get("LEADER")
        member_role_id = updated_guild["roles"].get("MEMBER")
        leader_role = self.guild.get_role(leader_role_id) if leader_role_id else None
        member_role = self.guild.get_role(member_role_id) if member_role_id else None

        for reg_id in old_clan["active_registrant_ids"]:
            registrant = updated_guild["clan_registrants"][reg_id]
            member = self.guild.get_member(registrant["member_id"])

            if member is None:
                continue

            await member.remove_roles(leader_role, member_role)

        active_registrants = [
            reg for reg in updated_guild["clan_registrants"].values()
            if reg["id"] in self.clan_config["active_registrant_ids"]
        ]

        for reg in active_registrants:
            member = self.guild.get_member(reg["member_id"])

            if member is None:
                continue

            leader_registrant = updated_guild["clan_registrants"][
                self.clan_config["leader_registrant_id"]
            ]

            if leader_role is not None and member.id == leader_registrant["member_id"]:
                await member.add_roles(leader_role)

            if member_role is not None:
                await member.add_roles(member_role)

        await self.message.edit(content="Clan change approved.", view=None)
        pass

    @discord.ui.button(label="Reject", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()

        await self.config.guild(self.guild).clear_raw(
            "pending_clan_edits", self.clan_config["id"]
        )
        await self.config.guild(self.guild).clear_raw(
            "pending_clan_registrant_edits", self.clan_config["leader_registrant_id"]
        )

        for registrant_id in self.clan_config["active_registrant_ids"]:
            await self.config.guild(self.guild).clear_raw(
                "pending_clan_registrant_edits", registrant_id
            )

        await self.message.edit(content="Clan change rejected.", view=None)
        pass


class ClanApprovalMessage:
    def __init__(
        self,
        guild: discord.Guild,
        config: Config,
        bot: commands.Bot,
        message: discord.Message,
        clan_draft: PendingClanConfigDraft,
        registrant_drafts: typing.Dict[str, PendingClanRegistrationConfigDraft],
    ):
        self.message = message
        self.bot = bot
        self.guild = guild
        self.clan_draft = clan_draft
        self.registrant_drafts = registrant_drafts
        self.config = config

    async def collect(self):
        changes = ""

        original_clan_config : ClanConfig = await self.config.guild(self.guild).get_raw(
            "clans", self.clan_draft["id"]
        )

        if original_clan_config["is_active"] != self.clan_draft["is_active"]:
            changes += (
                f"Status: `{'Active' if original_clan_config['is_active'] else 'Inactive'}` -> `{'Active' if self.clan_draft['is_active'] else 'Inactive'}`\n"
            )

        if original_clan_config["name"] != self.clan_draft["name"]:
            changes += f"Name: `{original_clan_config['name']}` -> `{self.clan_draft['name']}`\n"

        if original_clan_config["description"] != self.clan_draft["description"]:
            changes += f"Description: `{original_clan_config['description']}` -> `{self.clan_draft['description']}`\n"

        if original_clan_config["icon_url"] != self.clan_draft["icon_url"]:
            changes += f"Icon: `{original_clan_config['icon_url']}` -> `{self.clan_draft['icon_url']}`\n"

        if (
            original_clan_config["leader_registrant_id"]
            != self.clan_draft["leader_registrant_id"]
        ):
            old_leader_registrant = await self.config.guild(self.guild).get_raw(
                "clan_registrants", original_clan_config["leader_registrant_id"]
            )
            new_leader_registrant = self.registrant_drafts[
                self.clan_draft["leader_registrant_id"]
            ]

            old_leader_member = self.guild.get_member(
                old_leader_registrant["member_id"]
            )
            new_leader_member = self.guild.get_member(
                new_leader_registrant["member_id"]
            )

            changes += (
                f"Leader: {old_leader_member.mention} -> {new_leader_member.mention}\n"
            )

        new_members = []

        for registrant_id, registrant in self.registrant_drafts.items():
            if registrant_id not in original_clan_config["active_registrant_ids"]:
                new_members.append(registrant)

        if len(new_members) > 0:
            changes += "New Members: "
            changes += ",".join(
                [
                    f"{self.guild.get_member(member['member_id']).mention}"
                    for member in new_members
                ]
            )
            changes += "\n"

        removed_members = []

        for registrant_id in original_clan_config["active_registrant_ids"]:
            if registrant_id not in self.registrant_drafts.keys():
                found_registrant = await self.config.guild(self.guild).get_raw(
                    "clan_registrants", registrant_id
                )
                if found_registrant is None:
                    found_registrant = await self.config.guild(self.guild).get_raw(
                        "pending_clan_registrant_edits", registrant_id
                    )
                if found_registrant is None:
                    raise ValueError(
                        f"Registrant ID {registrant_id} not found in guild config for {self.guild.name}."
                    )
                removed_members.append(found_registrant)

        if len(removed_members) > 0:
            changes += "Removed Members: "
            changes += ",".join(
                [
                    f"{self.guild.get_member(member['member_id']).mention}"
                    for member in removed_members
                ]
            )
            changes += "\n"

        await self.message.edit(
            content=("Changes:\n" + changes) if changes != "" else "",
            embed=ClanDraftEmbed(
                guild=self.guild,
                clan_config=self.clan_draft,
                registrants=self.registrant_drafts,
            ),
            view=await ApproveClanDraftView(
                bot=self.bot,
                config=self.config,
                guild=self.guild,
                message=self.message,
                clan_config=self.clan_draft,
                clan_registrant_drafts=self.registrant_drafts,
            ).collect(),
        )


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
        super().__init__(timeout=300)

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
            await interaction.followup.send("Response has been recorded.  Awaiting both verifications.", ephemeral=True)
            await self.collect()
        else:
            self.submit.disabled = True
            self.cancel.disabled = True
            self.edit_stats.disabled = True
            self.winner.disabled = True
            self.player1_character.disabled = True
            self.player2_character.disabled = True

            await interaction.followup.send("Both players have verified the record.  Submitting.")

            await self.collect()
            embed = BattleRecordEmbed(
                ctx=self.ctx,
                guild_config=await self.config.guild(self.guild).all(),
                battle_record_id=self.battle_record_id,
            )

            await self.message.edit(embed=embed, view=None)

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
