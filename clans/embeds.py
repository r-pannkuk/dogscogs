from datetime import datetime
from types import SimpleNamespace
import typing
import discord

from redbot.core import commands

from dogscogs.constants import TIMEZONE

from .config import (
    MAX_CLAN_MEMBERS,
    ClanPointAward,
    ClanRegistrationConfig,
    GuildConfig,
    ClanConfig,
    MemberConfig,
    ClanBattleRecord,
    get_active_clan,
    get_active_clan_registrant,
    get_all_clan_registrants,
)
from .characters import Characters


class ClanDraftEmbed(discord.Embed):
    """
    Simplified view for editing details and drafts.
    """

    def __init__(
        self,
        *,
        guild: discord.Guild,
        clan_config: ClanConfig,
        registrants: typing.Dict[str, ClanRegistrationConfig],
    ):
        leader_registrant = registrants[str(clan_config["leader_registrant_id"])].copy()

        active_registrants = [
            registrants[str(reg_id)].copy()
            for reg_id in clan_config["active_registrant_ids"]
        ]

        leader_registrant["member"] = guild.get_member(leader_registrant["member_id"])
        for reg in active_registrants:
            reg["member"] = guild.get_member(reg["member_id"])

            if reg["member"] is None:
                reg["member"] = SimpleNamespace()
                reg["member"].id = reg["member_id"]
                reg["member"].mention = f"<@{reg['member_id']}>"
                reg["member"].name = str(reg["member_id"])

        super().__init__(
            title=f"Clan: {discord.utils.escape_markdown(clan_config['name'])}"
            + (" (INACTIVE)" if clan_config["is_active"] is False else ""),
            description=discord.utils.escape_markdown(clan_config["description"] or ""),
        )

        self.add_field(
            name="Leader",
            value=f"{leader_registrant['member'].mention} ({leader_registrant['member'].name})"
            if leader_registrant["member"] is not None
            else leader_registrant["member_id"],
            inline=False,
        )

        self.add_field(
            name=f"Active Members ({len(clan_config['active_registrant_ids'])}/{MAX_CLAN_MEMBERS})",
            value="\n".join(
                [
                    f"{reg['member'].mention} ({discord.utils.escape_markdown(reg['member'].name)})"
                    if reg["member"] is not None
                    else reg["member_id"]
                    for reg in active_registrants
                    if reg["id"] != leader_registrant["id"]
                ]
            ),
            inline=False,
        )

        self.set_thumbnail(url=clan_config["icon_url"])


class ClanDetailsEmbed(ClanDraftEmbed):
    """
    Details view shown with stats.
    """

    def __init__(
        self,
        *,
        ctx: commands.GuildContext,
        guild_config: GuildConfig,
        clan_id: typing.Optional[str] = None,
        clan_config: typing.Optional[ClanConfig] = None,
    ):
        if clan_id is None and clan_config is None:
            raise ValueError("Either a clan_id or a clan_config must be provided.")

        if clan_config is None:
            clan_config = guild_config["clans"][clan_id]

        if clan_id is None:
            clan_id = clan_config["id"]

        super().__init__(
            guild=ctx.guild,
            clan_config=clan_config,
            registrants=guild_config["clan_registrants"],
        )

        timestamp = ctx.message.created_at.astimezone(tz=TIMEZONE)

        clan_awards = [
            award
            for award in guild_config["clan_point_awards"].values()
            if award["clan_registrant_id"] in clan_config["active_registrant_ids"]
        ]
        clan_battles = [
            battle
            for battle in guild_config["clan_battle_records"].values()
            if (
                battle["player1_registrant_id"] in clan_config["active_registrant_ids"]
                or battle["player2_registrant_id"]
                in clan_config["active_registrant_ids"]
            )
            and (battle["player1_verified"] and battle["player2_verified"])
        ]

        wins = len(
            [
                battle
                for battle in clan_battles
                if battle["winner_id"] in (
                    reg["id"] for reg in guild_config["clan_registrants"].values()
                    if reg["clan_id"] == clan_config["id"]
                )
            ]
        )
        losses = len(clan_battles) - wins

        lifetime_stats = (
            f"__Points__: {sum([award['points'] for award in clan_awards])}\n"
        )
        lifetime_stats += f"__Battles__: {len(clan_battles)}\n"
        lifetime_stats += f"__Record__: {wins} W : {losses} L"

        self.add_field(name="Lifetime Stats", value=lifetime_stats, inline=False)

        this_month_awards = [
            award
            for award in clan_awards
            if datetime.fromtimestamp(award["created_at"]).month == timestamp.month
            and datetime.fromtimestamp(award["created_at"]).year == timestamp.year
        ]
        this_month_battles = [
            battle
            for battle in clan_battles
            if datetime.fromtimestamp(battle["created_at"]).month == timestamp.month
            and datetime.fromtimestamp(battle["created_at"]).year == timestamp.year
        ]

        month_wins = len(
            [
                battle
                for battle in this_month_battles
                if battle["winner_id"] in (
                    reg["id"] for reg in guild_config["clan_registrants"].values()
                    if reg["clan_id"] == clan_config["id"]
                )
            ]
        )
        month_losses = len(this_month_battles) - month_wins

        this_month_stats = (
            f"__Points__: {sum([award['points'] for award in this_month_awards])}\n"
        )
        this_month_stats += f"__Battles__: {len(this_month_battles)}\n"
        this_month_stats += f"__Record__: {month_wins} W : {month_losses} L"

        self.add_field(
            name=f"{clan_config['name']} {timestamp.strftime('%B')} Stats",
            value=this_month_stats,
            inline=False,
        )

        self.add_field(
            name=" ", inline=False, value=f"<t:{int(timestamp.timestamp())}:F>"
        )


class ClanRegistrantEmbed(discord.Embed):
    def __init__(
        self,
        *,
        ctx: commands.GuildContext,
        guild_config: GuildConfig,
        member: discord.Member,
        member_config: MemberConfig,
    ):
        timestamp = ctx.message.created_at.astimezone(tz=TIMEZONE)

        registrant = get_active_clan_registrant(guild_config, member_config)

        if registrant is not None:
            registrant = registrant.copy()

        all_registrants = get_all_clan_registrants(guild_config, member_config).copy()

        if registrant is None:
            super().__init__(
                title=f"{member.display_name}'s Clan Profile",
                description="This member has not joined a clan.",
            )
            return

        registrant["member"] = member

        super().__init__(
            title=f"{member.display_name}'s Clan Profile",
        )

        self.set_thumbnail(
            url=member.display_avatar.url
        )

        clan_config = get_active_clan(guild_config, member_config)

        if clan_config is not None:
            self.add_field(
                name="Clan",
                value=discord.utils.escape_markdown(clan_config["name"])
                + f" [{clan_config['id']}]"
                + (" (INACTIVE)" if clan_config["is_active"] is False else ""),
                inline=False,
            )

            clan_awards = [
                award
                for award in guild_config["clan_point_awards"].values()
                if award["clan_registrant_id"] == registrant["id"]
            ]
            clan_battles = [
                battle
                for battle in guild_config["clan_battle_records"].values()
                if (
                    battle["player1_registrant_id"] == registrant["id"]
                    or battle["player2_registrant_id"] == registrant["id"]
                )
                and (battle["player1_verified"] and battle["player2_verified"])
            ]

            wins = len(
                [
                    battle
                    for battle in clan_battles
                    if battle["winner_id"] == registrant["id"]
                ]
            )
            losses = len(clan_battles) - wins

            clan_lifetime_stats = (
                f"__Points__: {sum([award['points'] for award in clan_awards])}\n"
            )
            clan_lifetime_stats += f"__Battles__: {len(clan_battles)}\n"
            clan_lifetime_stats += f"__Record__: {wins} W : {losses} L"

            self.add_field(
                name=f"{clan_config['name']} Lifetime Stats",
                value=clan_lifetime_stats,
                inline=False,
            )

            this_month_awards = [
                award
                for award in clan_awards
                if datetime.fromtimestamp(award["created_at"]).month == timestamp.month
                and datetime.fromtimestamp(award["created_at"]).year == timestamp.year
            ]
            this_month_battles = [
                battle
                for battle in clan_battles
                if datetime.fromtimestamp(battle["created_at"]).month == timestamp.month
                and datetime.fromtimestamp(battle["created_at"]).year == timestamp.year
            ]

            month_wins = len(
                [
                    battle
                    for battle in this_month_battles
                    if battle["winner_id"] == registrant["id"]
                ]
            )
            month_losses = len(this_month_battles) - month_wins

            this_month_stats = (
                f"__Points__: {sum([award['points'] for award in this_month_awards])}\n"
            )
            this_month_stats += f"__Battles__: {len(this_month_battles)}\n"
            this_month_stats += f"__Record__: {month_wins} W : {month_losses} L"

            self.add_field(
                name=f"{timestamp.strftime('%B')} Stats",
                value=this_month_stats,
                inline=False,
            )

        combined_lifetime_points = sum(
            [
                sum(
                    [
                        award["points"]
                        for award in guild_config["clan_point_awards"].values()
                        if award["clan_registrant_id"] == reg["id"]
                    ]
                )
                for reg in all_registrants
            ]
        )
        combined_lifetime_battles = [
            b
            for battle_list in [
                [
                    battle
                    for battle in guild_config["clan_battle_records"].values()
                    if (
                        battle["player1_registrant_id"] == reg["id"]
                        or battle["player2_registrant_id"] == reg["id"]
                    ) and (
                        battle["player1_verified"] and battle["player2_verified"]
                    )
                ]
                for reg in all_registrants
            ]
            for b in battle_list
        ]

        combined_wins = len(
            [
                battle
                for battle in combined_lifetime_battles
                if battle["winner_id"] == registrant["id"]
            ]
        )
        combined_losses = len(combined_lifetime_battles) - combined_wins

        combined_lifetime_stats = f"__Points__: {combined_lifetime_points}\n"
        combined_lifetime_stats += f"__Battles__: {len(combined_lifetime_battles)}\n"
        combined_lifetime_stats += f"__Record__: {combined_wins} W : {combined_losses} L"

        self.add_field(
            name="Combined Lifetime Stats", value=combined_lifetime_stats, inline=False
        )


class BattleRecordEmbed(discord.Embed):
    def __init__(
        self,
        *,
        ctx: commands.GuildContext,
        guild_config: GuildConfig,
        battle_record_id: typing.Optional[int] = None,
        battle_record: typing.Optional[ClanBattleRecord] = None,
    ):
        if battle_record_id is None and battle_record is None:
            raise ValueError(
                "Either a battle_record_id or a battle_record must be provided."
            )

        if battle_record is None:
            battle_record = guild_config["clan_battle_records"][battle_record_id]

        if battle_record_id is None:
            battle_record_id = battle_record["id"]

        player1_registrant = guild_config["clan_registrants"][
            battle_record["player1_registrant_id"]
        ]
        player1 = ctx.guild.get_member(player1_registrant["member_id"])
        player2_registrant = guild_config["clan_registrants"][
            battle_record["player2_registrant_id"]
        ]
        player2 = ctx.guild.get_member(player2_registrant["member_id"])

        player1_clan = guild_config["clans"][player1_registrant["clan_id"]]
        player2_clan = guild_config["clans"][player2_registrant["clan_id"]]

        super().__init__(
            title=f"Battle Record: {battle_record_id}",
            description=f"{discord.utils.escape_markdown(player1_clan['name'])} vs. {discord.utils.escape_markdown(player2_clan['name'])}",
        )

        self.add_field(
            name=(
                f"{Characters[battle_record['player1_character']]['emoji']} "
                if battle_record["player1_character"]
                else ""
            )
            + f"{player1.display_name} ({discord.utils.escape_markdown(player1_clan['name'])})",
            value=f"__User__: {player1.mention}\n"
            + f"__Games Won__: {battle_record['player1_games_won']}\n"
            + f"__Verified__: {':white_check_mark:' if battle_record['player1_verified'] else ':x:'}\n"
            + f"__Character__: {Characters[battle_record['player1_character']]['full_name'] if battle_record['player1_character'] else ''}",
            inline=True,
        )

        self.add_field(
            name=(
                f"{Characters[battle_record['player2_character']]['emoji']} "
                if battle_record["player2_character"]
                else ""
            )
            + f"{player2.display_name} ({discord.utils.escape_markdown(player2_clan['name'])})",
            value=f"__User__: {player2.mention}\n"
            + f"__Games Won__: {battle_record['player2_games_won']}\n"
            + f"__Verified__: {':white_check_mark:' if battle_record['player2_verified'] else ':x:'}\n"
            + f"__Character__: {Characters[battle_record['player2_character']]['full_name'] if battle_record['player2_character'] else ''}",
            inline=True,
        )

        self.add_field(
            name="Winner",
            value=f"{player1.mention} ({discord.utils.escape_markdown(player1_clan['name'])})"
            if battle_record["winner_id"] == player1_registrant["id"]
            else f"{player2.mention} ({discord.utils.escape_markdown(player2_clan['name'])})"
            if battle_record["winner_id"] == player2_registrant["id"]
            else "None",
            inline=False,
        )

        self.set_footer(
            text=f"Created at {datetime.fromtimestamp(battle_record['created_at']).astimezone(tz=TIMEZONE)}"
        )


class ClanPointAwardEmbed(discord.Embed):
    def __init__(
        self,
        *,
        ctx: commands.GuildContext,
        guild_config: GuildConfig,
        award_id: typing.Optional[int] = None,
        award_config: typing.Optional[ClanPointAward] = None,
    ):
        if award_id is None and award_config is None:
            raise ValueError("Either an award_id or an award_config must be provided.")

        if award_config is None:
            award_config = guild_config["clan_point_awards"][award_id]

        if award_id is None:
            award_id = award_config["id"]

        award_config = guild_config["clan_point_awards"][award_id]
        registrant = guild_config["clan_registrants"][
            award_config["clan_registrant_id"]
        ]
        clan = guild_config["clans"][registrant["clan_id"]]
        member = ctx.guild.get_member(registrant["member_id"])

        super().__init__(
            title=f"Point Award: {award_id}",
            description=f"{member.mention} ({discord.utils.escape_markdown(clan['name'])})",
        )

        self.add_field(
            name="Points",
            value=award_config["points"],
            inline=False,
        )

        self.add_field(
            name="Reason",
            value=discord.utils.escape_markdown(award_config["reason"]),
            inline=False,
        )

        self.set_footer(
            text=f"Created at {award_config['created_at'].astimezone(tz=TIMEZONE)}"
        )
