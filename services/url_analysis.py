import re
from typing import List

# Basic URL regex – good enough for most mail content
URL_REGEX = re.compile(
    r"""(?i)\b((?:https?://|www\.)[^\s<>"]+)"""
)


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    urls = URL_REGEX.findall(text)
    # Normalize a bit: strip trailing punctuation
    cleaned = []
    for u in urls:
        cleaned.append(u.rstrip(').,;\'"'))
    # De-duplicate while preserving order
    seen = set()
    result = []
    for u in cleaned:
        if u not in seen:
            seen.add(u)
            result.append(u)
    return result