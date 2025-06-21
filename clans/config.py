from datetime import datetime
import typing

from .characters import CharacterID

MAX_CLAN_MEMBERS = 15

ChannelType = typing.Literal[
    'LEADERBOARD', 
    'CREATION', 
    'EDIT', 
    'EDIT_LOGS', 
    'APPLICATION', 
    'REPORT'
]

RoleType = typing.Literal[
    'LEADER',
    'MEMBER'
]

ChannelConfig = typing.Dict[ChannelType, typing.Optional[int]]
RoleConfig = typing.Dict[RoleType, typing.Optional[int]]

class GuildConfig(typing.TypedDict):
    clans: typing.Dict[str, 'ClanConfig']
    pending_clan_edits: typing.Dict[str, 'PendingClanConfigDraft']
    pending_clan_registrant_edits: typing.Dict[str, 'PendingClanRegistrationConfigDraft']
    clan_registrants: typing.Dict[str, 'ClanRegistrationConfig']
    clan_battle_records: typing.Dict[str, 'ClanBattleRecord']
    clan_point_awards: typing.Dict[str, 'ClanPointAward']
    channels: ChannelConfig
    leaderboard_message: typing.Optional['MessageConfig']
    roles: RoleConfig

class MessageConfig(typing.TypedDict):
    message_id: int
    channel_id: int

class MemberConfig(typing.TypedDict):
    clan_registrant_ids: typing.List[str]

class ClanConfig(typing.TypedDict):
    id: int
    is_active: bool
    name: str
    description: typing.Optional[str]
    leader_registrant_id: int
    active_registrant_ids: typing.List[str]
    icon_url: typing.Optional[str]

class PendingClanConfigDraft(ClanConfig):
    draft_created_at: datetime
    message_id: int
    channel_id: int

class ApplicationClanConfig(ClanConfig):
    message_id: int
    channel_id: int

class ClanRegistrationConfig(typing.TypedDict):
    id: int
    member_id: int
    clan_id: int
    created_at: datetime
    last_joined_at: datetime

class PendingClanRegistrationConfigDraft(ClanRegistrationConfig):
    draft_created_at: datetime
    message_id: int
    channel_id: int

class ClanBattleRecord(typing.TypedDict):
    id: int
    player1_registrant_id: int
    player1_character: typing.Optional[CharacterID]
    player1_games_won: typing.Optional[int]
    player1_verified: bool
    player2_registrant_id: int
    player2_character: typing.Optional[CharacterID]
    player2_games_won: typing.Optional[int]
    player2_verified: bool
    winner_id: int
    created_at: datetime

class ClanPointAward(typing.TypedDict):
    id: int
    clan_registrant_id: int
    points: int
    reason: typing.Optional[str]
    created_at: datetime

def get_active_clan(guild_config: 'GuildConfig', member_config: 'MemberConfig') -> typing.Optional['ClanConfig']:
    all_clans = [
        clan for clan in guild_config['clans'].values()
        if any([registrant_id in clan['active_registrant_ids'] for registrant_id in member_config['clan_registrant_ids']])
    ]

    if len(all_clans) == 1:
        return all_clans[0]
    elif len(all_clans) > 1:
        raise ValueError("Member is in multiple clans.")
    else:
        return None

def get_all_clan_registrants(guild_config: 'GuildConfig', member_config: 'MemberConfig') -> typing.List['ClanRegistrationConfig']:
    return [
        reg for reg in guild_config['clan_registrants'].values()
        if reg['id'] in member_config['clan_registrant_ids']
    ]

def get_active_clan_registrant(guild_config: 'GuildConfig', member_config: 'MemberConfig') -> typing.Optional['ClanRegistrationConfig']:
    """
    Returns a clan registrant if it's actively part of a clan.
    """
    possible_registrants = get_all_clan_registrants(guild_config, member_config)

    if len(possible_registrants) == 0:
        return None
    
    active_clan = get_active_clan(guild_config, member_config)

    if active_clan is None:
        return None
    
    return next(reg for reg in possible_registrants if reg['clan_id'] == active_clan['id'])