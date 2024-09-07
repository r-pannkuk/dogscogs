from enum import Enum
import typing

PaidEmojiType = typing.Union[typing.Literal['image'], typing.Literal['animated']]

class PaidEmojiConfig(typing.TypedDict):
    id: int
    type: PaidEmojiType
    author_id: int
    price: int
    source_url: str
    last_used_at: float
    used_count: int


class EmojiConfigurationPrompt(typing.TypedDict):
    name: str
    url: str
    type: PaidEmojiType