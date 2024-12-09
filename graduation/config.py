import typing

def get_registry_entry(id: int, registry: typing.List['RegisteredRole']):
    for entry in registry:
        if entry['role_id'] == id:
            return entry

    return None

def get_tail(head_id: int, registry: typing.List['RegisteredRole'], depth : typing.Optional[int] = 0) -> typing.Tuple[typing.Union[None,int], int]:
    """Fetches the tail_id of the last link in the linked list registry structure that is exclusive."""
    
    entry = get_registry_entry(head_id, registry)

    if entry is None:
        return None, depth
    
    if not entry['exclusive']:
        return None, depth

    if len(entry['next_ids']) == 0:
        return head_id, depth
    
    possible_nexts = [
        get_tail(next_id, registry, depth + 1)
        for next_id in entry['next_ids']
    ]

    possible_nexts = [x for x in possible_nexts if x[0] is not None]

    return max([
        get_tail(next_id, registry, depth + 1)
        for next_id in entry['next_ids']
    ], key=lambda x: x[1])


def get_role_depth(head_id: int, role_id: int, registry: typing.List['RegisteredRole']) -> int:
    """Determines the depth of the target role_id based on the head_id in the linked list registry structure."""
    depth = 0
    current_id = head_id
    while current_id != role_id:
        current_entry = get_registry_entry(current_id, registry)
        if current_entry is None:
            break
        if len(current_entry['next_ids']) == 0:
            break
        current_id = current_entry['next_ids'][0]
        depth += 1

    return depth

class GuildConfig(typing.TypedDict):
    enabled: bool
    head_id: typing.Union[None, int]
    registry: typing.List['RegisteredRole']
    responses: typing.List[str]

class RegisteredRole(typing.TypedDict):
    role_id: int
    next_ids: typing.List[int]
    exclusive: bool

class MemberConfig(typing.TypedDict):
    last_promotion_timestamp : typing.Union[None, float]
