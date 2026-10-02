from __future__ import annotations

import json
import re

WRAPPERS = {"ShallowReactive", "Reactive", "Ref", "ShallowRef", "EmptyRef", "EmptyShallowRef"}


def extract_payload(html: str) -> list:
    match = re.search(
        r'<script type="application/json"[^>]*id="__NUXT_DATA__"[^>]*>(.*?)</script>',
        html,
    )
    if match is None:
        raise RuntimeError("На странице ПФК ЦСКА нет данных календаря")
    payload = json.loads(match.group(1))
    if not isinstance(payload, list):
        raise RuntimeError("Данные календаря ПФК ЦСКА в неожиданном формате")
    return payload


def revive(payload: list):
    cache: dict[int, object] = {}

    def resolve(index: int, stack: set[int]):
        if index in cache:
            return cache[index]
        if index < 0:
            return None
        if index >= len(payload):
            raise RuntimeError(f"Битая ссылка в данных ПФК ЦСКА: {index}")
        if index in stack:
            return None
        stack.add(index)
        value = payload[index]
        if isinstance(value, list):
            if (
                value
                and isinstance(value[0], str)
                and value[0] in WRAPPERS
                and len(value) == 2
                and isinstance(value[1], int)
            ):
                cache[index] = None
                revived = resolve(value[1], stack)
                cache[index] = revived
                stack.discard(index)
                return revived
            if value and value[0] == "Set" and len(value) <= 1:
                cache[index] = []
                stack.discard(index)
                return cache[index]
            items: list = []
            cache[index] = items
            for item in value:
                items.append(resolve(item, stack) if isinstance(item, int) else item)
            stack.discard(index)
            return items
        if isinstance(value, dict):
            obj: dict = {}
            cache[index] = obj
            for key, item in value.items():
                obj[key] = resolve(item, stack) if isinstance(item, int) else item
            stack.discard(index)
            return obj
        cache[index] = value
        stack.discard(index)
        return value

    return resolve(0, set())
