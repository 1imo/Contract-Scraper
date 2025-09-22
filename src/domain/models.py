from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    agency: str
    category: str  # e.g., IT
    status: str
    detail_url: str
    description: Optional[str] = None
