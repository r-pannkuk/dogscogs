import typing

OperatorType = typing.Literal["set", "add", "multiply"]
BonusType = typing.Literal['normal']
KeyType = typing.Literal['rolecolors', 'nyame', 'curse']

class Modifier(typing.TypedDict):
    key: KeyType
    operator: OperatorType
    type: BonusType
    value: int

class Equipment(typing.TypedDict):
    id: int
    name: str
    description: str
    modifiers: typing.List[Modifier]

class Race(typing.TypedDict):
    id: int
    name: str
    description: str
    modifiers: typing.List[Modifier]

class BattlerConfig(typing.TypedDict):
    attacker_wins_ties: bool
    attacker_roll: str
    defender_roll: str
    equipment: typing.List[Equipment]
    races: typing.List[Race]

class BattleUserConfig(typing.TypedDict):
    equipment_ids: typing.List[int]
    race_id: int