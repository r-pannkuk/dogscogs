import typing

class GuildConfig(typing.TypedDict):
    enabled: bool
    registered_role_ids: typing.List[int]
    assigned_role_id : typing.Union[None, int]
    registered_role_count: int
    responses: typing.List[str]