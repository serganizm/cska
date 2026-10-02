from __future__ import annotations

import urllib.error
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


def fetch_text(url: str, *, xhr: bool = False, timeout: int = 40) -> str:
    headers = {
        "User-Agent": USER_AGENT,
        "Accept-Language": "ru,en;q=0.8",
    }
    if xhr:
        headers["X-Requested-With"] = "XMLHttpRequest"
        headers["Accept"] = "text/html, */*"
    request = urllib.request.Request(url, headers=headers)
    last_error: Exception | None = None
    for _ in range(2):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            last_error = error
    raise RuntimeError(f"Не удалось открыть {url}") from last_error
