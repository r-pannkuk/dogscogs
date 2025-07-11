from datetime import datetime
from typing import Literal, get_type_hints
import typing
import uuid
from discord.ext import tasks

from clans.views.clans import ClanApprovalMessage, EditClanDraftView
from clans.views.scoreboard import ScoreboardPaginatedEmbed, generate_page
from clans.views.scores import CreateBattleReportView

from .config import (
    ChannelType,
    ClanBattleRecord,
    ClanRegistrationConfig,
    GuildConfig,
    MemberConfig,
    ClanConfig,
    PendingClanConfigDraft,
    PendingClanRegistrationConfigDraft,
    RoleType,
    get_active_clan,
    get_active_clan_registrant,
)
from .embeds import (
    BattleRecordEmbed,
    ClanDetailsEmbed,
    ClanDraftEmbed,
    ClanRegistrantEmbed,
)

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER, TIMEZONE
from dogscogs.views.paginated import PaginatedEmbed
from dogscogs.core.converter import DogCogConverter

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

REFRESH_INTERVAL_SECS = 60 * 10 # 10 minutes
MINIMUM_BATTLES_BETWEEN_REPORT = 2

DEFAULT_GUILD: GuildConfig = {
    "clans": {},
    "pending_clan_edits": {},
    "pending_clan_registrant_edits": {},
    "clan_registrants": {},
    "clan_battle_records": {},
    "clan_point_awards": {},
    "channels": {},
    "roles": {},
}

DEFAULT_MEMBER: MemberConfig = {
    "clan_registrant_ids": [],
}


class ClanConverter(DogCogConverter):
    @staticmethod
    async def parse(ctx: commands.GuildContext, input: str) -> ClanConfig:  # type: ignore[override]
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Clans",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        try:
            guild_config: GuildConfig = await config.guild(ctx.guild).all()
            return next(
                c
                for c in guild_config["clans"].values()
                if (
                    str(c["id"]) == input or c["name"].lower().find(input.lower()) != -1
                )
            )
        except StopIteration as exc:
            raise commands.BadArgument(
                f"`{input}` is not a clan found in {ctx.guild.name}."
            ) from exc


class Clans(commands.Cog):
    """
    Clan ownership and organization.
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

    @commands.hybrid_group()
    @commands.guild_only()
    async def clans(self, ctx: commands.GuildContext) -> None:
        """
        Lists all clans in the server.
        """
        pass

    @clans.group(with_app_command=False)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def settings(self, ctx: commands.GuildContext):
        """
        Configure clan settings.
        """
        pass

    async def _get_or_set_channel(
        self,
        ctx: commands.GuildContext,
        channel_type: ChannelType,
        channel: typing.Optional[discord.TextChannel],
    ) -> discord.TextChannel:
        """
        Gets or sets if provided the configuration channel for the given type.

        Parameters:
        - ctx: The context to send messages to.
        - type: The type of channel to get or set.
        - channel: The channel to set if provided.
        """
        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        if channel is None:
            channel_id = guild_config["channels"].get(channel_type, None)
            if channel_id is None:
                return None
            return ctx.guild.get_channel(channel_id)

        await self.config.guild(ctx.guild).channels.set_raw(channel_type, value=channel.id)
        return channel

    async def _get_or_set_role(
        self,
        ctx: commands.GuildContext,
        role_type: RoleType,
        role: typing.Optional[discord.Role],
    ) -> discord.Role:
        """
        Gets or sets if provided the configuration role for the given type.

        Parameters:
        - ctx: The context to send messages to.
        - type: The type of role to get or set.
        - role: The role to set if provided.
        """
        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        if role is None:
            role_id = guild_config["roles"].get(role_type, None)
            if role_id is None:
                return None
            return ctx.guild.get_role(role_id)

        await self.config.guild(ctx.guild).roles.set_raw(role_type, value=role.id)
        return role

    @settings.command(with_app_command=False, name="channels")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channels(self, ctx: commands.GuildContext):
        """
        List all configured channels.
        """
        embed = discord.Embed(
            title="Configured Channels",
            color=discord.Color.blue(),
        )

        description = ""

        for t in typing.get_args(ChannelType):
            channel = await self._get_or_set_channel(ctx, t, None)
            description += f"**__{t.capitalize()}__**: {channel.mention if channel else 'Not Set'}\n"

        embed.description = description

        await ctx.send(embed=embed)

    @settings.command(with_app_command=False, name="leaderboard")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_leaderboard(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Set or see the channel for leaderboard viewing.
        """
        channel = await self._get_or_set_channel(ctx, "LEADERBOARD", channel)

        if channel is not None:
            await ctx.send(f"Leaderboard channel set to {channel.mention}.")

            leaderboard_message_config = await self.config.guild(ctx.guild).get_raw("leaderboard_message", default=None)

            if leaderboard_message_config is not None:
                if leaderboard_message_config["channel_id"] == channel.id:
                    return
                
                leaderboard_message = ctx.guild.get_channel(
                    leaderboard_message_config["channel_id"]
                ).get_partial_message(leaderboard_message_config["message_id"])

                if leaderboard_message is not None:
                    await leaderboard_message.delete()

            self.refresh_leaderboard.restart()
        else:
            await ctx.send("Leaderboard channel not set.")

    @settings.command(with_app_command=False, name="creation", aliases=["create"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_creation(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Set or see the channel for clan creation.
        """
        channel = await self._get_or_set_channel(ctx, "CREATION", channel)

        if channel is not None:
            await ctx.send(f"Clan creation channel set to {channel.mention}.")
        else:
            await ctx.send("Clan creation channel not set.")

    @settings.command(with_app_command=False, name="edit")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_edit(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Set or see the channel for clan editing.
        """
        channel = await self._get_or_set_channel(ctx, "EDIT", channel)

        if channel is not None:
            await ctx.send(f"Clan edit channel set to {channel.mention}.")
        else:
            await ctx.send("Clan edit channel not set.")

    @settings.command(with_app_command=False, name="logs")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_logs(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Set or see the channel for clan logs.
        """
        channel = await self._get_or_set_channel(ctx, "EDIT_LOGS", channel)

        if channel is not None:
            await ctx.send(f"Clan edit logs channel set to {channel.mention}.")
        else:
            await ctx.send("Clan edit logs channel not set.")

    @settings.command(
        with_app_command=False, name="application", aliases=["applications"]
    )
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_application(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Set or see the channel for clan applications.
        """
        channel = await self._get_or_set_channel(ctx, "APPLICATION", channel)

        if channel is not None:
            await ctx.send(f"Clan applications channel set to {channel.mention}.")
        else:
            await ctx.send("Clan applications channel not set.")

    @settings.command(with_app_command=False, name="reports", aliases=["report"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_reports(
        self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]
    ):
        """
        Set or see the channel for clan battle reports.
        """
        channel = await self._get_or_set_channel(ctx, "REPORT", channel)

        if channel is not None:
            await ctx.send(f"Clan battle reports channel set to {channel.mention}.")
        else:
            await ctx.send("Clan battle reports channel not set.")

    @settings.command(with_app_command=False, name="roles")
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def roles(self, ctx: commands.GuildContext):
        """
        List all configured roles.
        """
        embed = discord.Embed(
            title="Configured Roles",
            color=discord.Color.blue(),
        )

        description = ""

        for t in typing.get_args(RoleType):
            role = await self.config.guild(ctx.guild).roles.get_raw(t, default=None)
            description += f"**__{t.capitalize()}__**: {ctx.guild.get_role(role).mention if role else 'Not Set'}\n"

        embed.description = description

        await ctx.send(embed=embed)

    @settings.command(with_app_command=False, name="leader", aliases=["leaders"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role_leader(
        self, ctx: commands.GuildContext, role: typing.Optional[discord.Role]
    ):
        """
        Set or see the role for clan leaders.
        """
        role = await self._get_or_set_role(ctx, "LEADER", role)

        if role is not None:
            await ctx.send(f"Clan Leader role set to {role.mention}.")
        else:
            await ctx.send("Clan Leader role not set.")

    @settings.command(with_app_command=False, name="member", aliases=["members"])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def role_member(
        self, ctx: commands.GuildContext, role: typing.Optional[discord.Role]
    ):
        """
        Set or see the role for clan members.
        """
        role = await self._get_or_set_role(ctx, "MEMBER", role)

        if role is not None:
            await ctx.send(f"Clan Member role set to {role.mention}.")
        else:
            await ctx.send("Clan Member role not set.")

    @clans.command(with_app_command=False)
    @commands.guild_only()
    @commands.is_owner()
    async def reset(self, ctx: commands.GuildContext):
        """
        Reset all clan data.
        """
        await self.config.clear_all_guilds()
        await self.config.clear_all_members()
        await ctx.send("All clan data has been reset.")

    @clans.command(aliases=["ccreate"], with_app_command=True)
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def create(
        self,
        ctx: commands.GuildContext,
        leader: discord.Member,
        name: str,
        description: typing.Optional[str] = None,
        icon_url: typing.Optional[str] = None,
    ):
        """
        Create a new clan.
        """
        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        if not ctx.interaction:
            await ctx.send(
                "This command is now a slash command. Please use the new format.",
                ephemeral=True,
                delete_after=10,
            )
            return

        if ctx.channel.id != guild_config["channels"].get("CREATION", None):
            creation_channel_id = guild_config["channels"].get("CREATION", None)
            if creation_channel_id is not None:
                creation_channel = ctx.guild.get_channel(creation_channel_id)
                if creation_channel is not None:
                    return await ctx.reply(
                        f"Please create clans in {creation_channel.mention}.",
                        delete_after=10,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
            else:
                return await ctx.reply(
                    "The clan creation channel is not set.",
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions.none(),
                )

        if any(
            [c["name"].lower() == name.lower() for c in guild_config["clans"].values()]
        ):
            return await ctx.send(f"Clan {name} already exists.")

        new_clan: ClanConfig = {
            "id": str(uuid.uuid4().int),
            "name": name,
            "description": description,
            "icon_url": icon_url,
            "is_active": True,
        }

        new_registrant: ClanRegistrationConfig = {
            "id": str(uuid.uuid4().int),
            "member_id": leader.id,
            "clan_id": new_clan["id"],
            "created_at": ctx.message.created_at.timestamp(),
            "last_joined_at": ctx.message.created_at.timestamp(),
        }

        new_clan["leader_registrant_id"] = new_registrant["id"]
        new_clan["active_registrant_ids"] = [new_registrant["id"]]

        old_registrant_ids = await self.config.member(leader).clan_registrant_ids()
        old_registrant_ids.append(new_registrant["id"])
        await self.config.member(leader).clan_registrant_ids.set(
            list(set(old_registrant_ids))
        )

        await self.config.guild(ctx.guild).clan_registrants.set_raw(
            new_registrant["id"], value=new_registrant
        )
        await self.config.guild(ctx.guild).clans.set_raw(new_clan["id"], value=new_clan)

        updated_guild: GuildConfig = await self.config.guild(ctx.guild).all()

        for clan in updated_guild["clans"].values():
            if clan["id"] != new_clan["id"]:
                clan["active_registrant_ids"] = list(
                    set(
                        [
                            reg_id
                            for reg_id in clan["active_registrant_ids"]
                            if reg_id not in old_registrant_ids
                        ]
                    )
                )

                if clan["leader_registrant_id"] in old_registrant_ids:
                    clan["is_active"] = False

                await self.config.guild(ctx.guild).set_raw(
                    "clans", clan["id"], value=clan
                )

        message = await ctx.send(
            embed=ClanDraftEmbed(
                guild=ctx.guild,
                registrants={new_registrant["id"]: new_registrant},
                clan_config=new_clan,
            ),
        )

        await message.edit(
            view=await EditClanDraftView(
                ctx=ctx,
                message=message,
                config=self.config,
                author_id=ctx.author.id,
                bot=self.bot,
                clan_config=new_clan,
                guild=ctx.guild,
            ).collect()
        )

    @clans.command(with_app_command=False)
    @commands.guild_only()
    async def edit(
        self,
        ctx: commands.GuildContext,
        *,
        clan: typing.Optional[typing.Annotated[ClanConfig, ClanConverter]],
    ):
        """
        Edit a clan.
        """

        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        if clan is None:
            clan = get_active_clan(
                guild_config, await self.config.member(ctx.author).all()
            )

            if clan is None:
                return await ctx.send("You are not in a clan.")

        registrant_config = get_active_clan_registrant(
            guild_config, await self.config.member(ctx.author).all()
        )

        if not ctx.author.guild_permissions.manage_roles and (
            registrant_config is None
            or clan["leader_registrant_id"] != registrant_config["id"]
        ):
            return await ctx.send(
                f"You are not the leader of clan **{discord.utils.escape_markdown(clan['name'])}**."
            )

        # Get preexisting drafts if exist
        pending_clan_edits: typing.Dict[
            str, PendingClanConfigDraft
        ] = await self.config.guild(ctx.guild).pending_clan_edits()
        pending_clan_registrant_edits: typing.Dict[
            str, PendingClanRegistrationConfigDraft
        ] = await self.config.guild(ctx.guild).pending_clan_registrant_edits()

        registrants = {
            r["id"]: r
            for r in guild_config["clan_registrants"].values()
            if r["clan_id"] == clan["id"]
        }

        if str(clan["id"]) in pending_clan_edits:
            clan = pending_clan_edits[str(clan["id"])]

        for registrant in pending_clan_registrant_edits.values():
            if registrant["clan_id"] == clan["id"]:
                registrants[registrant["id"]] = registrant

        message = await ctx.send(
            embed=ClanDraftEmbed(
                guild=ctx.guild, clan_config=clan, registrants=registrants
            ),
        )

        await message.edit(
            view=await EditClanDraftView(
                ctx=ctx,
                message=message,
                config=self.config,
                author_id=ctx.author.id,
                bot=self.bot,
                clan_config=clan,
                guild=ctx.guild,
            ).collect()
        )

    async def clan_info(self, ctx: commands.GuildContext, clan: ClanConfig):
        """
        Display info about a clan.
        """
        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        registrant_config = get_active_clan_registrant(
            guild_config, await self.config.member(ctx.author).all()
        )

        message = await ctx.send(
            embed=ClanDetailsEmbed(
                ctx=ctx, guild_config=guild_config, clan_id=str(clan["id"])
            )
        )

        if (
            registrant_config is not None
            and clan["leader_registrant_id"] == registrant_config["id"]
        ):
            await message.edit(
                view=await EditClanDraftView(
                    ctx=ctx,
                    message=message,
                    config=self.config,
                    author_id=ctx.author.id,
                    bot=self.bot,
                    clan_config=clan,
                    guild=ctx.guild,
                ).collect()
            )

    async def member_info(self, ctx: commands.GuildContext, member: discord.Member):
        """
        Display info about a user.
        """

        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        member_config: MemberConfig = await self.config.member(member).all()

        embed = ClanRegistrantEmbed(
            ctx=ctx,
            guild_config=guild_config,
            member=member,
            member_config=member_config,
        )

        await ctx.send(embed=embed)

    @clans.command(with_app_command=False)
    @commands.guild_only()
    async def info(
        self,
        ctx: commands.GuildContext,
        *,
        query: typing.Union[
            typing.Optional[discord.Member],
            typing.Optional[typing.Annotated[ClanConfig, ClanConverter]],
        ],
    ):
        if isinstance(query, discord.Member):
            await self.minfo(ctx, query)
            return
        elif isinstance(query, dict) and all(
            key in query for key in get_type_hints(ClanConfig).keys()
        ):
            await self.cinfo(ctx, query)
            return
        else:
            active_clan = get_active_clan(
                await self.config.guild(ctx.guild).all(),
                await self.config.member(ctx.author).all(),
            )

            if active_clan is not None:
                await self.clan_info(ctx, active_clan)
                return

            await self.member_info(ctx, ctx.author)

    @clans.command(aliases=["myinfo", "memberinfo"], with_app_command=False)
    @commands.guild_only()
    async def minfo(
        self, ctx: commands.GuildContext, member: typing.Optional[discord.Member]
    ):
        await self.member_info(ctx, member or ctx.author)

    @clans.command(with_app_command=False)
    @commands.guild_only()
    async def cinfo(
        self,
        ctx: commands.GuildContext,
        clan: typing.Optional[typing.Annotated[ClanConfig, ClanConverter]],
    ):
        """
        Display info about a clan.
        """
        if clan is None:
            clan = get_active_clan(
                await self.config.guild(ctx.guild).all(),
                await self.config.member(ctx.author).all(),
            )

            if clan is None:
                return await ctx.send("You are not in a clan.")

        await self.clan_info(ctx, clan)

    @clans.command(with_app_command=False)
    @commands.guild_only()
    async def list(self, ctx: commands.GuildContext):
        """
        List all clans in the server.
        """

        async def get_page(page: int):
            guild_config = await self.config.guild(ctx.guild).all()

            if not guild_config["clans"] or len(guild_config["clans"].keys()) == 0:
                return discord.Embed(
                    title="No Clans",
                    description=f"There are no clans found in {ctx.guild.name}.",
                    color=discord.Color.red(),
                ), 1

            embed = ClanDetailsEmbed(
                ctx=ctx,
                guild_config=guild_config,
                clan_id=[k for k in guild_config["clans"].keys()][page],
            )

            embed.set_footer(
                text=f"Clan {page + 1}/{len(guild_config['clans'].keys())}"
            )
            return embed, len(guild_config["clans"].keys())

        await PaginatedEmbed(
            message=ctx.message,
            get_page=get_page,
        ).send()

    @clans.command(with_app_command=True)
    @commands.guild_only()
    async def report(
        self,
        ctx: commands.GuildContext,
        player1: discord.Member,
        player2: discord.Member,
    ):
        """
        Submit a match report for clan scorekeeping.
        """

        guild_config: GuildConfig = await self.config.guild(ctx.guild).all()

        if not ctx.interaction:
            await ctx.send(
                "This command is now a slash command. Please use the new format.",
                ephemeral=True,
                delete_after=10,
            )
            return

        if ctx.channel.id != guild_config["channels"].get("REPORT", None):
            report_channel_id = guild_config["channels"].get("REPORT", None)
            if report_channel_id is not None:
                report_channel = ctx.guild.get_channel(report_channel_id)
                if report_channel is not None:
                    await ctx.reply(
                        f"Please submit reports in {report_channel.mention}.",
                        delete_after=10,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                    return
            else:
                await ctx.reply(
                    "The report channel is not set.",
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
                return

        if not ctx.author.guild_permissions.manage_roles:
            if ctx.author != player1 and ctx.author != player2:
                await ctx.reply(
                    "You don't have permission to submit reports for other members.",
                    delete_after=10,
                )
                return

            author_config: MemberConfig = await self.config.member(ctx.author).all()

            if get_active_clan(guild_config, author_config) is None:
                await ctx.reply(
                    "You are not currently part of a clan.", delete_after=10
                )
                return
            
            opponent = player1 if player1.id != ctx.author.id else player2

            author_registrant_ids = await self.config.member(ctx.author).clan_registrant_ids()
            opponent_registrant_ids = await self.config.member(opponent).clan_registrant_ids()

            battle_records = guild_config["clan_battle_records"]
            battle_records = sorted(filter(
                lambda record: (
                    record["player1_registrant_id"] in author_registrant_ids or
                    record["player2_registrant_id"] in author_registrant_ids
                ) and record["player2_verified"] and record["player1_verified"],
                battle_records.values(),
            ), key=lambda record: (
                record["created_at"], record["id"],
            ), reverse=True)

            these_two_battle_records = list(filter(
                lambda record: (
                    (record["player1_registrant_id"] in author_registrant_ids and record["player2_registrant_id"] in opponent_registrant_ids) or
                    (record["player1_registrant_id"] in opponent_registrant_ids and record["player2_registrant_id"] in author_registrant_ids)
                ),
                battle_records
            ))
            last_battle_record = these_two_battle_records[0] if len(these_two_battle_records) > 0 else None

            if last_battle_record is not None:
                for i in range(0, MINIMUM_BATTLES_BETWEEN_REPORT):
                    if i >= len(battle_records):
                        break
                    
                    if battle_records[i]['id'] == last_battle_record['id']:
                        won : bool = (
                            battle_records[i]["winner_id"] in author_registrant_ids
                        )
                        await ctx.reply(
                            f"You have already submitted a report recently for {player1.mention} and {player2.mention}.\n"
                            f"Why don't you stop {'bullying' if won else 'inting at'} {opponent.mention} and fight someone {'your own size' if won else 'more your level'}?\n"
                            f"(Submit battles for {MINIMUM_BATTLES_BETWEEN_REPORT - i} different opponents first).",
                            delete_after=20,
                            allowed_mentions=discord.AllowedMentions.none(),
                        )
                        return
                
        if player1.id == player2.id:
            await ctx.reply(
                "Stop hitting yourself, idiot.",
                delete_after=10,
                allowed_mentions=discord.AllowedMentions.none(),
            )
            return

        player1_config: MemberConfig = await self.config.member(player1).all()
        player2_config: MemberConfig = await self.config.member(player2).all()

        error_response = ""

        player1_active_registrant: ClanRegistrationConfig = get_active_clan_registrant(
            guild_config, player1_config
        )

        if player1_active_registrant is None:
            error_response += (
                f"{player1.mention} doesn't have an active clan registration.  "
            )

        player2_active_registrant: ClanRegistrationConfig = get_active_clan_registrant(
            guild_config, player2_config
        )

        if player2_active_registrant is None:
            error_response += (
                f"{player2.mention} doesn't have an active clan registration.  "
            )

        if player1_active_registrant["clan_id"] == player2_active_registrant["clan_id"]:
            error_response += (
                f"{player1.mention} and {player2.mention} are in the same clan.  "
            )

        if error_response != "":
            await ctx.reply(
                f"{error_response}\nAbandoning record.",
                allowed_mentions=discord.AllowedMentions.none(),
                delete_after=10,
            )
            return

        new_battle_record: ClanBattleRecord = {
            "id": str(uuid.uuid4().int),
            "player1_registrant_id": player1_active_registrant["id"],
            "player1_character": None,
            "player1_games_won": None,
            "player1_verified": False,
            "player2_registrant_id": player2_active_registrant["id"],
            "player2_character": None,
            "player2_games_won": None,
            "player2_verified": False,
            "winner_id": None,
            "created_at": ctx.message.created_at.timestamp(),
        }

        await self.config.guild(ctx.guild).clan_battle_records.set_raw(
            new_battle_record["id"], value=new_battle_record
        )

        guild_config = await self.config.guild(ctx.guild).all()

        message = await ctx.send(
            content=f"{player1.mention} and {player2.mention}, please verify the results below:",
            embed=BattleRecordEmbed(
                ctx=ctx,
                guild_config=guild_config,
                battle_record_id=new_battle_record["id"],
            ),
        )

        await message.edit(
            view=await CreateBattleReportView(
                ctx=ctx,
                message=message,
                config=self.config,
                author_id=ctx.author.id,
                bot=self.bot,
                battle_record_id=new_battle_record["id"],
                guild=ctx.guild,
            ).collect()
        )

        pass

    @clans.command(aliases=["sb", "leaderboard", "lb"], with_app_command=False)
    @commands.guild_only()
    async def scoreboard(self, ctx: commands.GuildContext):
        """
        Display the clan scoreboard.
        """
        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if guild_config["channels"].get("LEADERBOARD", None) is not None:
            leaderboard_channel = ctx.guild.get_channel(
                guild_config["channels"]["LEADERBOARD"]
            )
            if leaderboard_channel is not None and ctx.channel.id != leaderboard_channel.id:
                return await ctx.reply(
                    f"Please view the scoreboard in {leaderboard_channel.mention}.",
                    delete_after=10,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
        
        await ScoreboardPaginatedEmbed(
            config=self.config,
            interaction=ctx.interaction,
            original_message=ctx.message,
        ).send()
        pass

    @tasks.loop(seconds=REFRESH_INTERVAL_SECS)
    async def refresh_leaderboard(self):
        """
        Refresh the leaderboard message in the configured channel.
        """
        for guild in self.bot.guilds:
            leaderboard_channel_id = await self.config.guild(guild).channels.get_raw("LEADERBOARD", default=None)
            if leaderboard_channel_id is None:
                continue

            channel = guild.get_channel(leaderboard_channel_id)
            if channel is None:
                continue

            original_message_config = await self.config.guild(guild).get_raw("leaderboard_message", default=None)
            message = None

            if original_message_config is not None:
                try:
                    message = await channel.fetch_message(
                        original_message_config["message_id"]
                    )
                except Exception:
                    pass

            if message is None:
                message = await channel.send("Loading")

            clan_embed, _ = await generate_page(
                index=0,
                config=self.config,
                guild=guild,
            )

            member_embed, _ = await generate_page(
                index=0,
                config=self.config,
                guild=guild,
                type_choice="members",
            )

            clan_embed.title = f"{clan_embed.title} - Clans"
            clan_embed.set_footer(text=f"Updated at: {datetime.now(tz=TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")

            member_embed.title = f"{member_embed.title} - Members"
            member_embed.set_footer(text=f"Updated at: {datetime.now(tz=TIMEZONE).strftime('%Y-%m-%d %H:%M:%S')}")

            message = await message.edit(content=None, embeds=[clan_embed, member_embed])

            await self.config.guild(guild).set_raw("leaderboard_message", value={
                "message_id": message.id,
                "channel_id": channel.id,
            })

    async def cog_load(self):
        for guild in self.bot.guilds:
            pending_clan_edits: typing.Dict[
                str, PendingClanConfigDraft
            ] = await self.config.guild(guild).pending_clan_edits()
            pending_clan_registrant_edits: typing.Dict[
                str, PendingClanRegistrationConfigDraft
            ] = await self.config.guild(guild).pending_clan_registrant_edits()

            for clan_draft in pending_clan_edits.values():
                message = await self.bot.get_channel(
                    clan_draft["channel_id"]
                ).fetch_message(clan_draft["message_id"])
                registrant_drafts = {
                    str(registrant["id"]): registrant
                    for registrant in pending_clan_registrant_edits.values()
                    if str(registrant["clan_id"]) == str(clan_draft["id"])
                }

                await ClanApprovalMessage(
                    message=message,
                    config=self.config,
                    bot=self.bot,
                    clan_draft=clan_draft,
                    registrant_drafts=registrant_drafts,
                    guild=guild,
                ).collect()

        self.refresh_leaderboard.start()

    async def cog_unload(self):
        self.refresh_leaderboard.cancel()