import json
import os
from typing import List
from ...domain.models import Listing

STATE_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "..", "data", "state.json")
STATE_PATH = os.path.abspath(STATE_PATH)


class JsonStateRepository:
    def load_last_snapshot(self) -> List[Listing]:
        try:
            with open(STATE_PATH, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return [Listing(**item) for item in raw]
        except FileNotFoundError:
            return []

    def save_snapshot(self, listings: List[Listing]) -> None:
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump([l.__dict__ for l in listings], f, ensure_ascii=False, indent=2)
