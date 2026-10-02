from __future__ import annotations

import json
import re
from datetime import datetime

from bs4 import BeautifulSoup

from cska.http_client import fetch_text
from cska.model import MSK, Match

CALENDAR_URL = "https://cska-hockey.ru/calendar/"
SITE = "https://cska-hockey.ru"

MONTHS = {
    "января": 1,
    "февраля": 2,
    "марта": 3,
    "апреля": 4,
    "мая": 5,
    "июня": 6,
    "июля": 7,
    "августа": 8,
    "сентября": 9,
    "октября": 10,
    "ноября": 11,
    "декабря": 12,
}


def fetch_hockey() -> list[Match]:
    html = fetch_text(CALENDAR_URL)
    season = _current_season(html)
    start_year, end_year = (int(part) for part in season["name"].split("-"))
    months: list[int] = season["monthes"]
    december_at = months.index(12) if 12 in months else len(months) - 1
    found: dict[str, Match] = {}
    for index, month in enumerate(months):
        year = start_year if index <= december_at else end_year
        fragment = fetch_text(
            f"{CALENDAR_URL}?list=1&month={month}&year={year}",
            xhr=True,
        )
        for match in _parse_month(fragment, start_year, end_year, months, december_at):
            found[match.source_id] = match
    return list(found.values())


def _current_season(html: str) -> dict:
    marker = "datepickerData"
    start = html.find(marker)
    if start < 0:
        raise RuntimeError("На сайте ХК ЦСКА нет списка сезонов")
    bracket = html.find("[", start)
    if bracket < 0:
        raise RuntimeError("Список сезонов ХК ЦСКА не разобран")
    data, _ = json.JSONDecoder().raw_decode(html[bracket:])
    if not isinstance(data, list) or not data:
        raise RuntimeError("Список сезонов ХК ЦСКА пуст")
    season = data[-1]
    if "name" not in season or "monthes" not in season:
        raise RuntimeError("Текущий сезон ХК ЦСКА без месяцев")
    return season


def _parse_month(html: str, start_year: int, end_year: int, months: list[int], december_at: int) -> list[Match]:
    soup = BeautifulSoup(html, "html.parser")
    matches: list[Match] = []
    for event in soup.select("div.event.event--horizontal"):
        match = _parse_event(event, start_year, end_year, months, december_at)
        if match is not None:
            matches.append(match)
    return matches


def _season_year(month: int, start_year: int, end_year: int, months: list[int], december_at: int) -> int:
    if month in months:
        return start_year if months.index(month) <= december_at else end_year
    return start_year if month >= 8 else end_year


def _parse_event(event, start_year: int, end_year: int, months: list[int], december_at: int) -> Match | None:
    date_node = event.select_one(".event__date")
    if date_node is None:
        return None
    day_month = _parse_day_month(date_node.get_text(" ", strip=True))
    if day_month is None:
        return None
    day, month = day_month
    year = _season_year(month, start_year, end_year, months, december_at)
    opponent, city = _opponent(event)
    if not opponent:
        return None
    location = event.select_one(".event__location")
    venue = " ".join(location.get_text(" ", strip=True).split()) if location else ""
    time_node = event.select_one(".event__time")
    time_text = time_node.get_text(" ", strip=True) if time_node else ""
    starts_at = None
    date_from = None
    date_to = None
    if re.fullmatch(r"\d{1,2}:\d{2}", time_text):
        starts_at = datetime(year, month, day, *map(int, time_text.split(":")), tzinfo=MSK)
    else:
        played_on = datetime(year, month, day).date()
        date_from = played_on
        date_to = played_on
    score = _our_score(event)
    link = event.select_one("a[href*='/match/']")
    href = link.get("href") if link else ""
    match_id = ""
    if href:
        found = re.search(r"/match/(\d+)/", href)
        match_id = found.group(1) if found else href.strip("/")
    if not match_id:
        match_id = f"{year}-{month:02d}-{day:02d}-{opponent}"
    source_url = href if href.startswith("http") else SITE + href if href.startswith("/") else CALENDAR_URL
    return Match(
        sport="hockey",
        source_id=match_id,
        opponent=opponent,
        tournament="КХЛ",
        venue=venue,
        home_away="home" if _is_cska_arena(venue) else "away",
        starts_at=starts_at,
        date_from=date_from,
        date_to=date_to,
        score=score,
        source_url=source_url,
        opponent_city=city,
    )


def _our_score(event) -> str | None:
    result_node = event.select_one(".event__result")
    result = result_node.get_text(" ", strip=True) if result_node else ""
    found = re.fullmatch(r"(\d+)\s*:\s*(\d+)", result)
    if found is None:
        return None
    left, right = int(found.group(1)), int(found.group(2))
    names = []
    for member in event.select(".event__member"):
        name_node = member.select_one(".event__member-name")
        names.append(name_node.get_text(" ", strip=True) if name_node else "")
    cska_at = next((index for index, name in enumerate(names) if "ЦСКА" in name.upper()), None)
    if cska_at == 1:
        left, right = right, left
    return f"{left}:{right}"


def _opponent(event) -> tuple[str, str]:
    for member in event.select(".event__member"):
        name_node = member.select_one(".event__member-name")
        name = name_node.get_text(" ", strip=True) if name_node else ""
        if not name or "ЦСКА" in name.upper():
            continue
        location = member.select_one(".event__member-location")
        city = location.get_text(" ", strip=True) if location else ""
        return name, city
    return "", ""


def _parse_day_month(text: str) -> tuple[int, int] | None:
    match = re.search(r"(\d{1,2})\s+([а-яё]+)", text.lower())
    if match is None:
        return None
    month = MONTHS.get(match.group(2))
    if month is None:
        return None
    return int(match.group(1)), month


def _is_cska_arena(venue: str) -> bool:
    compact = venue.upper().replace("Ё", "Е").replace(" ", "")
    return "ЦСКААРЕНА" in compact
