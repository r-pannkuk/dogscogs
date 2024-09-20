import typing

OperatorType = typing.Literal["set", "add", "multiply"]
BonusType = typing.Literal['attack', 'defend', 'both']
KeyType = typing.Literal['rolecolors', 'nyame', 'curse']

class Modifier(typing.TypedDict):
    key: KeyType
    operator: OperatorType
    type: BonusType
    value: float

class Equipment(typing.TypedDict):
    id: int
    name: str
    description: str
    cost: int
    image_url: str
    modifiers: typing.List[Modifier]

class Race(typing.TypedDict):
    id: int
    name: str
    description: str
    image_url: str
    modifiers: typing.List[Modifier]

class BattlerConfig(typing.TypedDict):
    attacker_wins_ties: bool
    attacker_roll: str
    defender_roll: str
    use_embed: bool
    equipment: typing.List[Equipment]
    races: typing.List[Race]

class BattleUserConfig(typing.TypedDict):
    equipment_ids: typing.List[int]
    race_id: int
    race_chosen: bool