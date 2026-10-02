from __future__ import annotations

import argparse
import functools
import http.server
import traceback

from cska.export_ics import write_ics
from cska.export_web import write_matches_json
from cska.fetch_basket import fetch_basketball
from cska.fetch_football import fetch_football
from cska.fetch_hockey import fetch_hockey
from cska.store import ROOT, diff_schedule, load_all, load_sports, replace_sports
from cska.telegram import notify

FETCHERS = (
    ("football", fetch_football),
    ("hockey", fetch_hockey),
    ("basketball", fetch_basketball),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Календарь матчей ЦСКА")
    parser.add_argument("command", nargs="?", default="update", choices=("update", "serve"))
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)
    if args.command == "serve":
        return serve(args.port)
    return update()


def update() -> int:
    collected: dict[str, list] = {}
    errors: list[str] = []
    for sport, fetcher in FETCHERS:
        try:
            matches = fetcher()
            collected[sport] = matches
            print(f"{sport}: {len(matches)}")
        except Exception as error:
            errors.append(f"{sport}: {error}")
            print(f"{sport}: ошибка — {error}")
            traceback.print_exc()
    if not collected:
        print("Ни один календарь не прочитан")
        return 1
    previous = load_sports(set(collected))
    fresh = [match for matches in collected.values() for match in matches]
    changes = diff_schedule(previous, fresh) if previous else []
    replace_sports(collected)
    stored = load_all()
    write_matches_json(stored)
    write_ics(stored)
    print(f"В базе {len(stored)} матчей, изменений: {len(changes)}")
    try:
        notify(stored, changes)
    except Exception as error:
        errors.append(f"telegram: {error}")
        print(f"telegram: ошибка — {error}")
    if errors:
        print("Сбор завершён с ошибками:")
        for line in errors:
            print(f"  {line}")
        return 1
    return 0


def serve(port: int) -> int:
    web = ROOT / "web"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(web))
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    print(f"Календарь: http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0
