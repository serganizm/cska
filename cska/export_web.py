from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cska.model import MSK, Match
from cska.store import ROOT, sort_key

JSON_PATH = ROOT / "web" / "matches.json"


def write_matches_json(matches: list[Match], updated_at: datetime | None = None) -> Path:
    moment = updated_at or datetime.now(MSK)
    payload = {
        "updated_at": moment.isoformat(),
        "matches": [match.to_json() for match in sorted(matches, key=sort_key)],
    }
    JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    JSON_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return JSON_PATH
