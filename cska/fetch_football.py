from __future__ import annotations

from cska.http_client import fetch_text
from cska.model import Match, parse_msk_date, parse_msk_datetime
from cska.nuxt import extract_payload, revive

CALENDAR_URL = "https://pfc-cska.com/ru/matchi/kalendar-matchej/"
SITE = "https://pfc-cska.com"


def fetch_football() -> list[Match]:
    html = fetch_text(CALENDAR_URL)
    root = revive(extract_payload(html))
    page = _calendar_page(root)
    raw_matches = page.get("results") or []
    if not isinstance(raw_matches, list):
        raise RuntimeError("Календарь ПФК ЦСКА не содержит списка матчей")
    matches = [_match_from_api(item) for item in raw_matches]
    return [item for item in matches if item is not None]


def _calendar_page(root: object) -> dict:
    data = root.get("data") if isinstance(root, dict) else None
    if not isinstance(data, dict):
        raise RuntimeError("Календарь ПФК ЦСКА не разобран")
    for value in data.values():
        if not isinstance(value, dict):
            continue
        results = value.get("results")
        if (
            isinstance(results, list)
            and results
            and isinstance(results[0], dict)
            and "match_datetime" in results[0]
        ):
            return value
    raise RuntimeError("На странице ПФК ЦСКА не найден список матчей")


def _match_from_api(item: dict) -> Match | None:
    if not isinstance(item, dict) or not item.get("id"):
        return None
    opponent, city = _opponent(item)
    if not opponent:
        return None
    date_unknown = bool(item.get("match_date_not_determined"))
    time_unknown = bool(item.get("match_time_not_determined"))
    exact = None if date_unknown or time_unknown else parse_msk_datetime(item.get("match_datetime"))
    date_from = None
    date_to = None
    if exact is None:
        date_from = parse_msk_date(item.get("match_approximate_date_from"))
        date_to = parse_msk_date(item.get("match_approximate_date_to"))
        if date_from is None:
            date_from = parse_msk_date(item.get("match_datetime"))
        if date_to is None:
            date_to = date_from
        if date_from and date_to and date_to < date_from:
            date_from, date_to = date_to, date_from
    stadium = item.get("match_stadium") or {}
    tournament = item.get("match_tournament") or {}
    url = item.get("url") or ""
    if url.startswith("/"):
        url = SITE + url
    score = _our_score(item)
    return Match(
        sport="football",
        source_id=str(item["id"]),
        opponent=opponent,
        tournament=(tournament.get("name") or "").strip() if isinstance(tournament, dict) else "",
        venue=(stadium.get("name") or "").strip() if isinstance(stadium, dict) else "",
        home_away="home" if item.get("match_is_home") else "away",
        starts_at=exact,
        date_from=date_from,
        date_to=date_to,
        score=score,
        source_url=url or CALENDAR_URL,
        opponent_city=city,
    )


def _our_score(item: dict) -> str | None:
    if not item.get("match_is_finished"):
        return None
    team_a = item.get("match_team_a") if isinstance(item.get("match_team_a"), dict) else {}
    team_b = item.get("match_team_b") if isinstance(item.get("match_team_b"), dict) else {}
    score_a = _as_int(item.get("match_team_a_score"))
    score_b = _as_int(item.get("match_team_b_score"))
    if score_a is None or score_b is None:
        return None
    if team_a.get("is_our_team") is True:
        ours, theirs = score_a, score_b
    elif team_b.get("is_our_team") is True:
        ours, theirs = score_b, score_a
    else:
        return None
    return f"{ours}:{theirs}"


def _as_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    return int(text) if text.isdigit() else None


def _opponent(item: dict) -> tuple[str, str]:
    teams = [item.get("match_team_a"), item.get("match_team_b")]
    for team in teams:
        if isinstance(team, dict) and team.get("is_our_team") is False and team.get("name"):
            return str(team["name"]).strip(), _city(team)
    for team in teams:
        if isinstance(team, dict) and team.get("name") and "ЦСКА" not in str(team["name"]):
            return str(team["name"]).strip(), _city(team)
    title = str(item.get("pagetitle") or "")
    for separator in ("—", "–", "-"):
        if separator in title:
            left, right = [part.strip() for part in title.split(separator, 1)]
            if "ЦСКА" in left:
                return right, ""
            if "ЦСКА" in right:
                return left, ""
    return "", ""


def _city(team: dict) -> str:
    city = team.get("city") or {}
    if isinstance(city, dict):
        return str(city.get("name") or "").strip()
    return ""
