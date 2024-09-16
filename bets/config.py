from datetime import datetime
import typing
import uuid

BetState = typing.Literal["config", "open", "closed", "cancelled", "resolved"]

class Better(typing.TypedDict):
    member_id: int
    bet_option_id: int
    bet_amount: int

class BetOption(typing.TypedDict):
    id: int
    option_name: str

class BetConfig(typing.TypedDict):
    id: int
    state: BetState
    author_id: int
    minimum_bet: int
    title: str
    description: str
    options: typing.List[BetOption]
    betters: typing.List[Better]
    base_value: int
    winning_option_id: typing.Union[int, None]
    created_at : float
    last_edited_at : typing.Union[float, None]
    closed_at : typing.Union[float, None]

class BetGuildConfig(typing.TypedDict):
    enabled: bool
    active_bets: typing.Dict[str, BetConfig]
    allowed_role_ids: typing.List[int]

def generate_bet_config(
    *,
    id: typing.Optional[int] = None,
    state: BetState = 'config',
    author_id: int,
    minimum_bet: int = 1,
    title: str,
    description: str,
    options: typing.List[BetOption] = [],
    winning_option_id: typing.Optional[int] = None,
    betters: typing.List[Better] = [],
    base_value: int = 0,
    created_at : datetime = datetime.now(),
    last_edited_at : typing.Optional[datetime] = None,
    closed_at : typing.Optional[datetime] = None,
) -> BetConfig:
    return {
        "id": id or uuid.uuid4().int,
        "state": state,
        "author_id": author_id,
        "minimum_bet": minimum_bet,
        "title": title,
        "description": description,
        "options": options,
        "winning_option_id": winning_option_id,
        "betters": betters,
        "base_value": base_value,
        "created_at": created_at.timestamp(),
        "last_edited_at": last_edited_at.timestamp() if last_edited_at else None,
        "closed_at": closed_at.timestamp() if closed_at else None,
    }