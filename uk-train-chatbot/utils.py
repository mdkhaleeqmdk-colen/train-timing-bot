
from __future__ import annotations
import re
from typing import Optional

CRS_ALIAS = {
    "kings cross": "KGX",
    "king's cross": "KGX",
    "kings x": "KGX",
    "cambridge": "CBG",
    "euston": "EUS",
    "manchester piccadilly": "MAN",
    "birmingham new street": "BHM",
}

_time_pattern = re.compile(r"(\d{1,2}):(\d{2})")

def guess_crs(text: str) -> Optional[str]:
    t = text.strip().lower()
    return CRS_ALIAS.get(t)

def extract_time(text: str) -> Optional[str]:
    m = _time_pattern.search(text)
    return m.group(0) if m else None
