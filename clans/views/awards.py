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
from dogscogs.constants.discord.views import MAX_SELECT_OPTIONS

from dogscogs.views.prompts import ValidImageURLTextInput, NumberPromptTextInput
from dogscogs.views.paginated import PaginatedEmbed, OnCallbackSelect

from ..characters import Characters

from ..config import (
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
from ..embeds import BattleRecordEmbed, ClanDraftEmbed, ClanScoreboardEmbed

MAX_CLAN_MEMBERS = 20