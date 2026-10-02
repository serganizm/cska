from __future__ import annotations

import re
from datetime import datetime

from bs4 import BeautifulSoup

from cska.http_client import fetch_text
from cska.model import MSK, Match

CALENDAR_URL = "https://cskabasket.ru/schedule/?all=Y"
SITE = "https://cskabasket.ru"

SHORT_MONTHS = {
    "янв": 1,
    "фев": 2,
    "мар": 3,
    "апр": 4,
    "май": 5,
    "июн": 6,
    "июл": 7,
    "авг": 8,
    "сен": 9,
    "окт": 10,
    "ноя": 11,
    "дек": 12,
}


def fetch_basketball() -> list[Match]:
    html = fetch_text(CALENDAR_URL)
    years = _month_years(html)
    soup = BeautifulSoup(html, "html.parser")
    matches: list[Match] = []
    for row in soup.select("div.match-row"):
        match = _parse_row(row, years)
        if match is not None:
            matches.append(match)
    if not matches:
        raise RuntimeError("Календарь ПБК ЦСКА пуст")
    return matches


def _month_years(html: str) -> dict[int, int]:
    found: dict[int, int] = {}
    for name, year in re.findall(r"([А-Яа-яЁё]{3})[’'`'](\d{2})", html):
        month = SHORT_MONTHS.get(name.lower())
        if month is not None:
            found[month] = 2000 + int(year)
    if not found:
        raise RuntimeError("На сайте ПБК ЦСКА нет годов календаря")
    return found


def _parse_row(row, years: dict[int, int]) -> Match | None:
    date_node = row.select_one(".match-date")
    if date_node is None:
        return None
    date_text = date_node.get_text(" ", strip=True)
    parsed = re.search(r"(\d{1,2})\s+([а-яё]{3})", date_text.lower())
    if parsed is None:
        return None
    month = SHORT_MONTHS.get(parsed.group(2))
    if month is None or month not in years:
        return None
    day = int(parsed.group(1))
    year = years[month]
    time_match = re.search(r"(\d{1,2}:\d{2})", date_text)
    starts_at = None
    date_from = None
    date_to = None
    if time_match:
        hour, minute = (int(part) for part in time_match.group(1).split(":"))
        starts_at = datetime(year, month, day, hour, minute, tzinfo=MSK)
    else:
        played_on = datetime(year, month, day).date()
        date_from = played_on
        date_to = played_on
    teams = []
    for node in row.select("a.team, div.team"):
        title = (node.get("title") or node.get_text(" ", strip=True)).strip()
        if title:
            teams.append(title)
    opponent = next((name for name in teams if name.upper() != "ЦСКА"), "")
    if not opponent:
        return None
    stadium_nodes = [node for node in row.select(".match-stadium") if node.get_text(" ", strip=True)]
    tournament = " ".join(stadium_nodes[0].get_text(" ", strip=True).split()) if stadium_nodes else ""
    venue = " ".join(stadium_nodes[1].get_text(" ", strip=True).split()) if len(stadium_nodes) > 1 else ""
    city = "Москва" if _is_moscow_club(opponent) else ""
    icon = row.select_one(".stadium-info")
    classes = icon.get("class") if icon else []
    if "icon-home" in classes:
        side = "home"
    else:
        side = "away"
    score = _score(row)
    link = row.select_one("a[href*='/game/']")
    href = link.get("href") if link else ""
    found = re.search(r"/game/(\d+)/", href or "")
    source_id = found.group(1) if found else f"{year}-{month:02d}-{day:02d}-{opponent}"
    source_url = href if href.startswith("http") else SITE + href if href.startswith("/") else CALENDAR_URL
    return Match(
        sport="basketball",
        source_id=source_id,
        opponent=opponent,
        tournament=tournament,
        venue=venue,
        home_away=side,
        starts_at=starts_at,
        date_from=date_from,
        date_to=date_to,
        score=score,
        source_url=source_url,
        opponent_city=city,
    )


def _is_moscow_club(name: str) -> bool:
    key = name.casefold().replace("ё", "е").strip()
    return key == "мба" or key.startswith("мба ") or key.startswith("мба-")


def _score(row) -> str | None:
    versus = row.select_one(".vs")
    if versus is None:
        return None
    numbers = []
    for span in versus.find_all("span"):
        if span.find("a") is not None:
            continue
        text = span.get_text(" ", strip=True)
        if text.isdigit():
            numbers.append(text)
    if len(numbers) < 2:
        return None
    left, right = numbers[0], numbers[1]
    teams = []
    for node in row.select("a.team, div.team"):
        title = (node.get("title") or node.get_text(" ", strip=True)).strip()
        if title:
            teams.append(title)
    cska_at = next((index for index, name in enumerate(teams) if name.upper() == "ЦСКА"), None)
    if cska_at == 1:
        left, right = right, left
    return f"{left}:{right}"
