from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")

SPORT_LABELS = {
    "football": "Футбол",
    "hockey": "Хоккей",
    "basketball": "Баскетбол",
}


MONTHS_GENITIVE = (
    "",
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

WEEKDAYS = (
    "понедельник",
    "вторник",
    "среда",
    "четверг",
    "пятница",
    "суббота",
    "воскресенье",
)


def ru_date(value: date) -> str:
    return f"{value.day} {MONTHS_GENITIVE[value.month]}"


@dataclass
class Match:
    sport: str
    source_id: str
    opponent: str
    tournament: str
    venue: str
    home_away: str
    starts_at: datetime | None
    date_from: date | None
    date_to: date | None
    score: str | None
    source_url: str
    opponent_city: str = ""

    def key(self) -> tuple[str, str]:
        return (self.sport, self.source_id)

    def sport_label(self) -> str:
        return SPORT_LABELS.get(self.sport, self.sport)

    def side_text(self) -> str:
        if self.home_away == "home":
            return "Дома"
        if self.in_moscow():
            return "Выезд (Москва)"
        return "Выезд"

    def in_moscow(self) -> bool:
        return _mentions_moscow(self.opponent_city)

    def result(self) -> str | None:
        if not self.score or ":" not in self.score:
            return None
        left, right = self.score.split(":", 1)
        if not left.isdigit() or not right.isdigit():
            return None
        ours, theirs = int(left), int(right)
        if ours > theirs:
            return "win"
        if ours < theirs:
            return "loss"
        return "draw"

    def time_text(self) -> str:
        if self.starts_at is None:
            return "не определено"
        return self.starts_at.astimezone(MSK).strftime("%H:%M")

    def when_text(self) -> str:
        if self.starts_at is not None:
            local = self.starts_at.astimezone(MSK)
            return f"{ru_date(local.date())}, {local.strftime('%H:%M')}"
        if self.date_from is None:
            return "дата не назначена"
        if self.date_to is None or self.date_to == self.date_from:
            return f"{ru_date(self.date_from)}, время не назначено"
        if self.date_from.month == self.date_to.month and self.date_from.year == self.date_to.year:
            window = f"{self.date_from.day}–{self.date_to.day} {MONTHS_GENITIVE[self.date_from.month]}"
        else:
            window = f"{ru_date(self.date_from)} – {ru_date(self.date_to)}"
        return f"{window}, время не назначено"

    def summary(self) -> str:
        opponent = self.opponent if not self.score else f"{self.opponent} {self.score}"
        venue = self.venue or "арена не указана"
        return f"{self.sport_label()}, {opponent}, {self.side_text()}, {venue}, {self.time_text()}"

    def schedule_tuple(self) -> tuple:
        start = self.starts_at.astimezone(MSK).isoformat() if self.starts_at else None
        return (
            self.opponent,
            self.tournament,
            self.venue,
            self.home_away,
            self.opponent_city,
            start,
            self.date_from.isoformat() if self.date_from else None,
            self.date_to.isoformat() if self.date_to else None,
        )

    def to_json(self) -> dict:
        return {
            "sport": self.sport,
            "sport_label": self.sport_label(),
            "source_id": self.source_id,
            "opponent": self.opponent,
            "tournament": self.tournament,
            "venue": self.venue,
            "home_away": self.home_away,
            "home_away_label": self.side_text(),
            "time_label": self.time_text(),
            "starts_at": self.starts_at.astimezone(MSK).isoformat() if self.starts_at else None,
            "date_from": self.date_from.isoformat() if self.date_from else None,
            "date_to": self.date_to.isoformat() if self.date_to else None,
            "score": self.score,
            "result": self.result(),
            "source_url": self.source_url,
            "when_text": self.when_text(),
        }


def _mentions_moscow(value: str) -> bool:
    text = (value or "").casefold().replace("ё", "е")
    return "москв" in text or text.strip() in {"мск", "moscow"}


def parse_msk_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    for fmt, size in (
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%dT%H:%M:%S", 19),
        ("%Y-%m-%dT%H:%M", 16),
    ):
        try:
            return datetime.strptime(text[:size], fmt).replace(tzinfo=MSK)
        except ValueError:
            continue
    return None


def parse_msk_date(value: str | None) -> date | None:
    moment = parse_msk_datetime(value) if value and len(value.strip()) > 10 else None
    if moment is not None:
        return moment.date()
    if not value:
        return None
    text = value.strip()[:10]
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None
