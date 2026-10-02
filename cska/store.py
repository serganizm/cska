from __future__ import annotations

import sqlite3
from datetime import date, datetime
from pathlib import Path

from cska.model import MSK, Match

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "matches.sqlite"


def connect() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS matches (
            sport TEXT NOT NULL,
            source_id TEXT NOT NULL,
            opponent TEXT NOT NULL,
            tournament TEXT NOT NULL,
            venue TEXT NOT NULL,
            home_away TEXT NOT NULL,
            starts_at TEXT,
            date_from TEXT,
            date_to TEXT,
            score TEXT,
            source_url TEXT NOT NULL,
            opponent_city TEXT NOT NULL DEFAULT '',
            PRIMARY KEY (sport, source_id)
        )
        """
    )
    columns = {row[1] for row in connection.execute("PRAGMA table_info(matches)")}
    if "opponent_city" not in columns:
        connection.execute("ALTER TABLE matches ADD COLUMN opponent_city TEXT NOT NULL DEFAULT ''")
    return connection


def load_sports(sports: set[str] | None = None) -> list[Match]:
    query = "SELECT * FROM matches"
    params: tuple = ()
    if sports:
        placeholders = ",".join("?" for _ in sports)
        query += f" WHERE sport IN ({placeholders})"
        params = tuple(sorted(sports))
    with connect() as connection:
        rows = connection.execute(query, params).fetchall()
    return [_from_row(row) for row in rows]


def load_all() -> list[Match]:
    return load_sports()


def replace_sports(matches_by_sport: dict[str, list[Match]]) -> None:
    with connect() as connection:
        for sport, matches in matches_by_sport.items():
            connection.execute("DELETE FROM matches WHERE sport = ?", (sport,))
            connection.executemany(
                """
                INSERT INTO matches (
                    sport, source_id, opponent, tournament, venue, home_away,
                    starts_at, date_from, date_to, score, source_url, opponent_city
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [_row(match) for match in matches],
            )


def diff_schedule(old: list[Match], new: list[Match]) -> list[str]:
    previous = {match.key(): match for match in old}
    lines: list[str] = []
    for match in sorted(new, key=sort_key):
        earlier = previous.get(match.key())
        if earlier is None:
            lines.append(f"Новый матч: {match.summary()}")
            continue
        if earlier.schedule_tuple() == match.schedule_tuple():
            continue
        bits: list[str] = []
        if (earlier.starts_at, earlier.date_from, earlier.date_to) != (
            match.starts_at,
            match.date_from,
            match.date_to,
        ):
            bits.append(f"было {earlier.when_text()}, стало {match.when_text()}")
        if earlier.venue != match.venue:
            bits.append(f"арена: {earlier.venue or 'не указана'} → {match.venue or 'не указана'}")
        if earlier.side_text() != match.side_text():
            bits.append(f"было {earlier.side_text()}, стало {match.side_text()}")
        if earlier.opponent != match.opponent:
            bits.append(f"соперник: {earlier.opponent} → {match.opponent}")
        if earlier.tournament != match.tournament:
            bits.append(f"турнир: {earlier.tournament or 'не указан'} → {match.tournament or 'не указан'}")
        if bits:
            sport = match.sport_label()
            lines.append(f"{sport}, {match.opponent}: " + "; ".join(bits))
    return lines


def _row(match: Match) -> tuple:
    return (
        match.sport,
        match.source_id,
        match.opponent,
        match.tournament,
        match.venue,
        match.home_away,
        match.starts_at.astimezone(MSK).isoformat() if match.starts_at else None,
        match.date_from.isoformat() if match.date_from else None,
        match.date_to.isoformat() if match.date_to else None,
        match.score,
        match.source_url,
        match.opponent_city,
    )


def _from_row(row: sqlite3.Row) -> Match:
    return Match(
        sport=row["sport"],
        source_id=row["source_id"],
        opponent=row["opponent"],
        tournament=row["tournament"],
        venue=row["venue"],
        home_away=row["home_away"],
        starts_at=datetime.fromisoformat(row["starts_at"]) if row["starts_at"] else None,
        date_from=date.fromisoformat(row["date_from"]) if row["date_from"] else None,
        date_to=date.fromisoformat(row["date_to"]) if row["date_to"] else None,
        score=row["score"],
        source_url=row["source_url"],
        opponent_city=row["opponent_city"] if "opponent_city" in row.keys() else "",
    )


def sort_key(match: Match):
    if match.starts_at is not None:
        return (match.starts_at, match.sport, match.opponent)
    if match.date_from is not None:
        return (datetime.combine(match.date_from, datetime.min.time(), tzinfo=MSK), match.sport, match.opponent)
    return (datetime.max.replace(tzinfo=MSK), match.sport, match.opponent)
