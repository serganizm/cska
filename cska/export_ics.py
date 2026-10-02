from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from cska.model import MSK, Match
from cska.store import ROOT

ICS_PATH = ROOT / "web" / "calendar.ics"


def write_ics(matches: list[Match], now: datetime | None = None) -> Path:
    moment = now or datetime.now(MSK)
    future = [
        match
        for match in matches
        if match.starts_at is not None and match.starts_at >= moment
    ]
    future.sort(key=lambda match: match.starts_at or moment)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//cska//match calendar//RU",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:ЦСКА",
        "X-WR-TIMEZONE:Europe/Moscow",
        "BEGIN:VTIMEZONE",
        "TZID:Europe/Moscow",
        "BEGIN:STANDARD",
        "DTSTART:19700101T000000",
        "TZOFFSETFROM:+0300",
        "TZOFFSETTO:+0300",
        "TZNAME:MSK",
        "END:STANDARD",
        "END:VTIMEZONE",
    ]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for match in future:
        start = match.starts_at.astimezone(MSK)
        end = start + timedelta(hours=2)
        description = "\n".join(
            [
                match.sport_label(),
                match.opponent,
                match.side_text(),
                match.venue or "арена не указана",
                match.time_text(),
            ]
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{match.sport}-{match.source_id}@cska.local",
                f"DTSTAMP:{stamp}",
                f"DTSTART;TZID=Europe/Moscow:{start.strftime('%Y%m%dT%H%M%S')}",
                f"DTEND;TZID=Europe/Moscow:{end.strftime('%Y%m%dT%H%M%S')}",
                f"SUMMARY:{_escape(match.sport_label() + ', ' + match.opponent)}",
                f"LOCATION:{_escape(match.venue)}",
                f"DESCRIPTION:{_escape(description)}",
                f"URL:{_escape(match.source_url)}",
                "END:VEVENT",
            ]
        )
    lines.append("END:VCALENDAR")
    ICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    body = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    ICS_PATH.write_text(body, encoding="utf-8")
    return ICS_PATH


def _escape(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )


def _fold(line: str) -> str:
    data = line.encode("utf-8")
    parts: list[str] = []
    limit = 75
    while len(data) > limit:
        cut = limit
        while cut > 0 and (data[cut] & 0xC0) == 0x80:
            cut -= 1
        if cut <= 0:
            cut = limit
        parts.append(data[:cut].decode("utf-8"))
        data = data[cut:]
        limit = 74
    parts.append(data.decode("utf-8"))
    return "\r\n ".join(parts)
