from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from cska.model import MSK, WEEKDAYS, Match, ru_date
from cska.store import ROOT


def load_env() -> None:
    path = ROOT / ".env"
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def notify(matches: list[Match], changes: list[str]) -> None:
    load_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        print("Telegram не настроен: пропущены TELEGRAM_BOT_TOKEN или TELEGRAM_CHAT_ID")
        return
    if changes:
        _send(token, chat_id, "Изменения в календаре ЦСКА\n" + "\n".join(f"• {_html(line)}" for line in changes))
    _send(token, chat_id, week_digest(matches))


def week_digest(matches: list[Match], today: datetime | None = None) -> str:
    moment = today or datetime.now(MSK)
    start = moment.date()
    end = start + timedelta(days=6)
    grouped: dict = {}
    for match in matches:
        day = _digest_day(match, start, end)
        if day is None:
            continue
        grouped.setdefault(day, []).append(match)
    if not grouped:
        return "Матчи ЦСКА на 7 дней\n\nНа ближайшие 7 дней матчей нет."
    lines = ["Матчи ЦСКА на 7 дней", ""]
    for day in sorted(grouped):
        lines.append(f"<b>{ru_date(day)}, {WEEKDAYS[day.weekday()]}</b>")
        for match in sorted(grouped[day], key=lambda item: (item.starts_at is None, item.starts_at or datetime.max.replace(tzinfo=MSK))):
            lines.append(_match_line(match))
        lines.append("")
    return "\n".join(lines).rstrip()


def _digest_day(match: Match, start, end):
    if match.starts_at is not None:
        day = match.starts_at.astimezone(MSK).date()
        return day if start <= day <= end else None
    if match.date_from is None:
        return None
    window_end = match.date_to or match.date_from
    if window_end < start or match.date_from > end:
        return None
    return max(match.date_from, start)


def _match_line(match: Match) -> str:
    title = match.club_name()
    if match.club_place():
        title = f"{title} ({match.club_place()})"
    opponent = _html(title if not match.score else f"{title} {match.score}")
    linked = f'<a href="{_html(match.source_url)}">{opponent}</a>'
    venue = _html(match.venue or "арена не указана")
    return "\n".join(
        [
            _html(match.sport_label()),
            linked,
            _html(match.side_text()),
            venue,
            _html(match.time_text()),
        ]
    )


def _html(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _send(token: str, chat_id: str, text: str) -> None:
    for part in _chunks(text):
        _post(token, chat_id, part)


def _chunks(text: str, limit: int = 3500) -> list[str]:
    blocks: list[str] = []
    current = ""
    for line in text.split("\n"):
        piece = line if not current else "\n" + line
        if len(current) + len(piece) > limit and current:
            blocks.append(current)
            current = line
        else:
            current += piece
    if current:
        blocks.append(current)
    return blocks or [text]


def _post(token: str, chat_id: str, text: str) -> None:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode()
    request = urllib.request.Request(url, data=payload)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = json.loads(response.read().decode())
    if not body.get("ok"):
        raise RuntimeError(f"Telegram не принял сообщение: {body}")
