"""Validate experimental object localization from the multimodal model."""
import json
import re
from typing import Any


def parse_box(answer: str) -> list[int] | None:
    """Parse a single normalized bounding box or an explicit null result."""
    text = answer.strip()
    match = re.fullmatch(r'```(?:json)?\s*(.*?)\s*```', text, re.S)
    if match:
        text = match.group(1)
    value: Any = json.loads(text)
    if not isinstance(value, dict) or set(value) != {'box'}:
        raise ValueError('Expected a JSON object with one box field')
    box = value['box']
    if box is None:
        return None
    if (not isinstance(box, list) or len(box) != 4 or
            any(type(n) is not int or not 0 <= n <= 1000 for n in box) or
            box[0] >= box[2] or box[1] >= box[3]):
        raise ValueError('Invalid normalized bounding box')
    return box
