from typing import Literal
import typing
import uuid

from .config import ChannelType, ClanBattleRecord, ClanRegistrationConfig, GuildConfig, MemberConfig, ClanConfig, PendingClanConfigDraft, PendingClanRegistrationConfigDraft, get_active_clan, get_active_clan_registrant
from .embeds import BattleRecordEmbed, ClanDetailsEmbed, ClanDraftEmbed, ClanRegistrantEmbed
from clans.views import ApproveClanDraftView, ClanApprovalMessage, CreateBattleReportView, EditClanDraftView

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config

from dogscogs.constants import COG_IDENTIFIER
from dogscogs.views.paginated import PaginatedEmbed
from dogscogs.core.converter import DogCogConverter

RequestType = Literal["discord_deleted_user", "owner", "user", "user_strict"]

DEFAULT_GUILD : GuildConfig = {
    "clans": {},
    "pending_clan_edits": {},
    "pending_clan_registrant_edits": {},
    "clan_registrants": {},
    "clan_battle_records": {},
    "clan_point_awards": {},
    "channels": {}
}

DEFAULT_MEMBER : MemberConfig = {
    "clan_registrant_ids": [],
}

class ClanConverter(DogCogConverter):
    @staticmethod
    async def parse(ctx: commands.GuildContext, input: str) -> ClanConfig: # type: ignore[override]
        config = Config.get_conf(
            cog_instance=None,
            cog_name="Clans",
            identifier=COG_IDENTIFIER,
            force_registration=True,
        )
        try:
            guild_config : GuildConfig = await config.guild(ctx.guild).all()
            return next(c for c in guild_config['clans'].values() if (str(c['id']) == input or c['name'].lower().find(input.lower()) != -1))
        except StopIteration as exc:
            raise commands.BadArgument(f"`{input}` is not a clan found in {ctx.guild.name}.") from exc

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

    async def _get_or_set_channel(self, ctx: commands.GuildContext, type: ChannelType, channel: typing.Optional[discord.TextChannel]) -> discord.TextChannel:
        """
        Gets or sets if provided the configuration channel for the given type.

        Parameters:
        - ctx: The context to send messages to.
        - type: The type of channel to get or set.
        - channel: The channel to set if provided.
        """
        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if channel is None:
            channel_id = guild_config['channels'].get(type, None)
            if channel_id is None:
                return None
            return ctx.guild.get_channel(channel_id)
        
        await self.config.guild(ctx.guild).channels.set_raw(type, value=channel.id)
        return channel
    
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
    async def channel_leaderboard(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
        """
        Set or see the channel for leaderboard viewing.
        """
        channel = await self._get_or_set_channel(ctx, "LEADERBOARD", channel)

        if channel is not None:
            await ctx.send(f"Leaderboard channel set to {channel.mention}.")
        else:
            await ctx.send("Leaderboard channel not set.")


    @settings.command(with_app_command=False, name="creation", aliases=['create'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_creation(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
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
    async def channel_edit(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
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
    async def channel_logs(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
        """
        Set or see the channel for clan logs.
        """
        channel = await self._get_or_set_channel(ctx, "EDIT_LOGS", channel)

        if channel is not None:
            await ctx.send(f"Clan edit logs channel set to {channel.mention}.")
        else:
            await ctx.send("Clan edit logs channel not set.")

    @settings.command(with_app_command=False, name="application", aliases=['applications'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_application(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
        """
        Set or see the channel for clan applications.
        """
        channel = await self._get_or_set_channel(ctx, "APPLICATION", channel)

        if channel is not None:
            await ctx.send(f"Clan applications channel set to {channel.mention}.")
        else:
            await ctx.send("Clan applications channel not set.")

    @settings.command(with_app_command=False, name="reports", aliases=['report'])
    @commands.guild_only()
    @commands.has_guild_permissions(manage_roles=True)
    async def channel_reports(self, ctx: commands.GuildContext, channel: typing.Optional[discord.TextChannel]):
        """
        Set or see the channel for clan battle reports.
        """
        channel = await self._get_or_set_channel(ctx, "REPORT", channel)

        if channel is not None:
            await ctx.send(f"Clan battle reports channel set to {channel.mention}.")
        else:
            await ctx.send("Clan battle reports channel not set.")
    

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


    @clans.command(aliases=['ccreate'], with_app_command=True)
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
        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if any([c['name'].lower() == name.lower() for c in guild_config['clans'].values()]):
            return await ctx.send(f"Clan {name} already exists.")
        
        new_clan : ClanConfig = {
            "id": str(uuid.uuid4().int),
            "name": name,
            "description": description,
            "icon_url": icon_url,
            "is_active": True,
        }
        
        new_registrant : ClanRegistrationConfig = {
            "id": str(uuid.uuid4().int),
            "member_id": leader.id,
            "clan_id": new_clan['id'],
            "created_at": ctx.message.created_at.timestamp(),
            "last_joined_at": ctx.message.created_at.timestamp(),
        }

        new_clan['leader_registrant_id'] = new_registrant['id']
        new_clan['active_registrant_ids'] = [new_registrant['id']]

        old_registrant_ids = await self.config.member(leader).clan_registrant_ids()
        old_registrant_ids.append(new_registrant['id'])
        await self.config.member(leader).clan_registrant_ids.set(list(set(old_registrant_ids)))

        await self.config.guild(ctx.guild).clan_registrants.set_raw(new_registrant['id'], value=new_registrant)
        await self.config.guild(ctx.guild).clans.set_raw(new_clan['id'], value=new_clan)

        updated_guild : GuildConfig = await self.config.guild(ctx.guild).all()
        
        for clan in updated_guild["clans"].values():
            if clan["id"] != new_clan["id"]:
                clan["active_registrant_ids"] = list(set(
                    [
                        reg_id for reg_id in clan["active_registrant_ids"]
                        if reg_id not in old_registrant_ids
                    ]
                ))

                if clan["leader_registrant_id"] in old_registrant_ids:
                    clan["is_active"] = False

                await self.config.guild(ctx.guild).set_raw("clans", clan["id"], value=clan)

        message = await ctx.send(
            embed=ClanDraftEmbed(
                guild=ctx.guild,
                registrants={new_registrant['id']: new_registrant},
                clan_config=new_clan
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
    async def edit(self, ctx: commands.GuildContext, *, clan: typing.Optional[typing.Annotated[ClanConfig, ClanConverter]]):
        """
        Edit a clan.
        """
        
        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if clan is None:
            clan = get_active_clan(guild_config, await self.config.member(ctx.author).all())

            if clan is None:
                return await ctx.send("You are not in a clan.")
            
        registrant_config = get_active_clan_registrant(guild_config, await self.config.member(ctx.author).all())

        if not ctx.author.guild_permissions.manage_roles and (
            registrant_config is None or clan["leader_registrant_id"] != registrant_config["id"]
        ):
            return await ctx.send(f"You are not the leader of clan **{discord.utils.escape_markdown(clan['name'])}**.")
        
        # Get preexisting drafts if exist
        pending_clan_edits : typing.Dict[str, PendingClanConfigDraft] = await self.config.guild(ctx.guild).pending_clan_edits()
        pending_clan_registrant_edits : typing.Dict[str, PendingClanRegistrationConfigDraft] = await self.config.guild(ctx.guild).pending_clan_registrant_edits()

        registrants = {
            r['id']: r
            for r in guild_config['clan_registrants'].values()
            if r['clan_id'] == clan['id']
        }

        if str(clan['id']) in pending_clan_edits:
            clan = pending_clan_edits[str(clan['id'])]

        for registrant in pending_clan_registrant_edits.values():
            if registrant['clan_id'] == clan['id']:
                registrants[registrant['id']] = registrant

        message = await ctx.send(
            embed=ClanDraftEmbed(
                guild=ctx.guild,
                clan_config=clan,
                registrants=registrants
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


    @clans.command(aliases=['cinfo'], with_app_command=False)
    async def info(self, ctx: commands.GuildContext, *, clan: typing.Optional[typing.Annotated[ClanConfig, ClanConverter]]):
        """
        Display info about a clan.
        """
        
        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if clan is None:
            clan = get_active_clan(guild_config, await self.config.member(ctx.author).all())

            if clan is None:
                return await ctx.send("You are not in a clan.")

        registrant_config = get_active_clan_registrant(guild_config, await self.config.member(ctx.author).all())

        message = await ctx.send(
            embed=ClanDetailsEmbed(
                ctx=ctx, 
                guild_config=guild_config, 
                clan_id=str(clan['id'])
            )
        )

        if registrant_config is not None and clan["leader_registrant_id"] == registrant_config["id"]:
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

    @clans.command(with_app_command=False)
    async def list(self, ctx: commands.GuildContext):
        """
        List all clans in the server.
        """
        async def get_page(page: int):
            guild_config = await self.config.guild(ctx.guild).all()

            if not guild_config['clans'] or len(guild_config['clans'].keys()) == 0:
                return discord.Embed(
                    title="No Clans", 
                    description=f"There are no clans found in {ctx.guild.name}.",
                    color=discord.Color.red()
                ), 1

            embed = ClanDetailsEmbed(
                ctx=ctx,
                guild_config=guild_config,
                clan_id=[k for k in guild_config['clans'].keys()][page],
            )

            embed.set_footer(text=f"Clan {page+1}/{len(guild_config['clans'].keys())}")
            return embed, len(guild_config['clans'].keys())
        
        await PaginatedEmbed(
            message=ctx.message,
            get_page=get_page,
        ).send()

    @clans.command(aliases=['myinfo', 'memberinfo'], with_app_command=False)
    async def minfo(self, ctx: commands.GuildContext, member: typing.Optional[discord.Member]):
        """
        Display info about a user. 
        """
        
        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if member is None:
            member = ctx.author

        member_config : MemberConfig = await self.config.member(member).all()

        embed = ClanRegistrantEmbed(ctx=ctx, guild_config=guild_config, member_config=member_config)

        await ctx.send(embed=embed)


    @clans.command(with_app_command=True)
    async def report(
        self, 
        ctx: commands.GuildContext, 
        player1: discord.Member, 
        player2: discord.Member
    ):
        """
        Submit a match report for clan scorekeeping. 
        """

        guild_config : GuildConfig = await self.config.guild(ctx.guild).all()

        if not ctx.author.guild_permissions.manage_roles:

            if ctx.author != player1 and ctx.author != player2:
                await ctx.reply("You don't have permission to submit reports for other members.", delete_after=10)
                return
            
            author_config : MemberConfig = await self.config.member(ctx.author).all()
            
            if get_active_clan(guild_config, author_config) is None:
                await ctx.reply("You are not currently part of a clan.", delete_after=10)
                return


        player1_config : MemberConfig = await self.config.member(player1).all()
        player2_config : MemberConfig = await self.config.member(player2).all()

        error_response = ""
        
        player1_active_registrant : ClanRegistrationConfig = get_active_clan_registrant(guild_config, player1_config)

        if player1_active_registrant is None:
            error_response += f"{player1.mention} doesn't have an active clan registration.  "

        player2_active_registrant : ClanRegistrationConfig = get_active_clan_registrant(guild_config, player2_config)

        if player2_active_registrant is None:
            error_response += f"{player2.mention} doesn't have an active clan registration.  "

        if player1_active_registrant['clan_id'] == player2_active_registrant['clan_id']:
            error_response += f"{player1.mention} and {player2.mention} are in the same clan.  "

        if error_response != "":
            await ctx.reply(f"{error_response}\nAbandoning record.", allowed_mentions=discord.AllowedMentions.none(), delete_after=10)
            return
        
        new_battle_record : ClanBattleRecord = {
            "id": str(uuid.uuid4().int),
            "player1_registrant_id": player1_active_registrant['id'],
            "player1_character": None,
            "player1_games_won": None,
            "player1_verified": False,
            "player2_registrant_id": player2_active_registrant['id'],
            "player2_character": None,
            "player2_games_won": None,
            "player2_verified": False,
            "winner_id": player1.id if player1.id == ctx.author.id else player2.id,
            "created_at": ctx.message.created_at.timestamp(),
        }

        await self.config.guild(ctx.guild).clan_battle_records.set_raw(new_battle_record['id'], value=new_battle_record)

        guild_config = await self.config.guild(ctx.guild).all()

        message = await ctx.send(
            content=f"{player1.mention} and {player2.mention}, please verify the results below:",
            embed=BattleRecordEmbed(
                ctx=ctx,
                guild_config=guild_config, 
                battle_record_id=new_battle_record['id'],
            )
        )

        await message.edit(
            view=await CreateBattleReportView(
                ctx=ctx,
                message=message,
                config=self.config,
                author_id=ctx.author.id,
                bot=self.bot,
                battle_record_id=new_battle_record['id'],
                guild=ctx.guild,
            ).collect()
        )

        pass

    async def cog_load(self):
        for guild in self.bot.guilds:
            pending_clan_edits : typing.Dict[str, PendingClanConfigDraft] = await self.config.guild(guild).pending_clan_edits()
            pending_clan_registrant_edits : typing.Dict[str, PendingClanRegistrationConfigDraft] = await self.config.guild(guild).pending_clan_registrant_edits()

            for clan_draft in pending_clan_edits.values():
                message = await self.bot.get_channel(clan_draft['channel_id']).fetch_message(clan_draft['message_id'])
                registrant_drafts = {
                    str(registrant["id"]): registrant
                    for registrant in pending_clan_registrant_edits.values()
                    if str(registrant['clan_id']) == str(clan_draft['id'])
                }

                await ClanApprovalMessage(
                    message=message,
                    config=self.config,
                    bot=self.bot,
                    clan_draft=clan_draft,
                    registrant_drafts=registrant_drafts,
                    guild=guild,
                ).collect()