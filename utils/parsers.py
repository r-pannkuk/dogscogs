import re
import typing

def parse_emoji_ids(content: str) -> typing.List[int]:
    """Parses emoji ID's from a string.

    Args:
        content (str): The string content to parse emojis from.

    Returns:
        typing.List[str]: A list of emojis.
    """
    found_emojis : typing.List[str] = re.findall(r'<:\w*:\d*>', content)
    result = [e.split(':')[2].replace('>', '') for e in found_emojis]
    return [int(r) for r in result]