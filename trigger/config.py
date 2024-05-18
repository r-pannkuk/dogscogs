
from enum import IntFlag, auto
import typing


COG_IDENTIFIER = 260288776360820736

class ReactType(IntFlag):
    MESSAGE = auto()
    JOIN = auto()
    KICK = auto()
    BAN = auto()
    LEAVE = auto()


class CooldownConfig(typing.TypedDict):
    mins: typing.Union[str, float]
    next: float
    last_timestamp: float


class EmbedConfig(typing.TypedDict):
    use_embed: bool
    title: typing.Optional[str]
    footer: typing.Optional[str]
    image_url: typing.Optional[str]
    color: typing.Optional[
        typing.Tuple[
            typing.Annotated[int, "[0,255]"],
            typing.Annotated[int, "[0,255]"],
            typing.Annotated[int, "[0,255]"],
        ]
    ]


class TriggerConfig(typing.TypedDict):
    type: ReactType
    chance: typing.Union[str, float]
    list: typing.Optional[typing.List[str]]


class ReactConfig(typing.TypedDict):
    enabled: bool
    always_list: typing.Optional[typing.List[typing.Union[str, int]]]
    channel_ids: typing.Optional[typing.List[typing.Union[str, int]]]
    cooldown: CooldownConfig
    embed: typing.Optional[EmbedConfig]
    responses: typing.List[str]
    name: str
    trigger: TriggerConfig


class ListenerConfig(typing.TypedDict):
    enabled: bool
    param_types: typing.Tuple


ListenerGroupConfig = typing.Mapping[type, typing.Mapping[str, ListenerConfig]]