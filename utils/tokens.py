from enum import UNIQUE, StrEnum, verify
import typing

import discord


@verify(UNIQUE)
class Token(StrEnum):
    MemberName = "$MEMBER_NAME$"
    ServerName = "$SERVER_NAME$"
    MemberCount = "$MEMBER_COUNT$"
    Action = "$ACTION$"


def replace_tokens(
    text: str,
    member: discord.Member,
    use_mentions: typing.Optional[bool] = False,
):
    return (
        text.replace(
            Token.MemberName.value,
            member.display_name if not use_mentions else member.mention,
        )
        .replace(Token.ServerName.value, member.guild.name)
        .replace(Token.MemberCount.value, str(member.guild.member_count))
    )
