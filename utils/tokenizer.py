import discord
import typing

MEMBER_NAME_TOKEN = "$MEMBER_NAME$"
SERVER_NAME_TOKEN = "$SERVER_NAME$"
MEMBER_COUNT_TOKEN = "$MEMBER_COUNT$"
ACTION_TOKEN = "$ACTION$"


def replace_tokens(text, member: discord.Member, use_mentions: typing.Optional[bool] = False, token: typing.Optional[str] = None):
    if token is not None:
        return text.replace(token, )
    return text.replace(
        MEMBER_NAME_TOKEN, member.display_name if not use_mentions else member.mention
    ).replace(
        SERVER_NAME_TOKEN, member.guild.name
    ).replace(
        MEMBER_COUNT_TOKEN, str(member.guild.member_count)
    )
