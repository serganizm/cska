from __future__ import annotations

import argparse
import http.server
import json
import threading
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


_refresh_lock = threading.Lock()


def serve(port: int) -> int:
    web = ROOT / "web"

    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(web), **kwargs)

        def do_POST(self):
            if self.path.split("?", 1)[0].rstrip("/") != "/refresh":
                self.send_error(404)
                return
            if not _refresh_lock.acquire(blocking=False):
                self._send_json(409, {"ok": False, "error": "refresh already running"})
                return
            try:
                code = update()
            except Exception as error:
                self._send_json(500, {"ok": False, "error": str(error)})
                return
            finally:
                _refresh_lock.release()
            self._send_json(200 if code == 0 else 502, {"ok": code == 0})

        def _send_json(self, status: int, payload: dict) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Календарь: http://127.0.0.1:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
    return 0
