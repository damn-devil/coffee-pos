#!/usr/bin/env python3
"""Забирает меню из общего канала синхронизации и обновляет menu.json."""

import json
import os
import urllib.request
from datetime import datetime, timezone

TOPIC = os.environ.get("SYNC_TOPIC", "coffee_pos_menu_9f4c1e7a2b")
EVENTS_URL = f"https://ntfy.sh/{TOPIC}/json?poll=1&since=all"
MENU_PATH = "menu.json"


def get(url: str) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "coffee-pos-menu-sync"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def fetch_menu() -> dict | None:
    raw = get(EVENTS_URL).decode("utf-8", "replace")
    for line in reversed([l.strip() for l in raw.splitlines() if l.strip()]):
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") not in (None, "message"):
            continue

        message = event.get("message") or ""
        if message.startswith("{"):
            try:
                return json.loads(message)
            except json.JSONDecodeError:
                pass

        attachment = event.get("attachment") or {}
        url = attachment.get("url")
        if url:
            try:
                return json.loads(get(url).decode("utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return None


def normalize(menu: dict) -> dict | None:
    if not isinstance(menu, dict):
        return None
    categories = menu.get("categories")
    products = menu.get("products")
    if not isinstance(categories, list) or not isinstance(products, list):
        return None

    clean_categories = []
    for category in categories:
        if isinstance(category, dict) and category.get("id") and category.get("name"):
            clean_categories.append({
                "id": str(category["id"]),
                "name": str(category["name"]),
                "emoji": str(category.get("emoji") or "📁"),
            })

    clean_products = []
    for product in products:
        if not isinstance(product, dict) or not product.get("id") or not product.get("name"):
            continue
        try:
            price = float(product.get("price") or 0)
        except (TypeError, ValueError):
            continue
        if price <= 0:
            continue
        clean_products.append({
            "id": str(product["id"]),
            "name": str(product["name"]),
            "category": str(product.get("category") or ""),
            "price": round(price),
            "desc": str(product.get("desc") or ""),
            "emoji": str(product.get("emoji") or "☕"),
        })

    if not clean_products:
        return None

    return {
        "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "categories": clean_categories,
        "products": clean_products,
    }


def main() -> None:
    menu = normalize(fetch_menu())
    if not menu:
        print("Меню в канале не найдено — пропускаем")
        return

    current = None
    if os.path.exists(MENU_PATH):
        try:
            with open(MENU_PATH, encoding="utf-8") as handle:
                current = json.load(handle)
        except (json.JSONDecodeError, OSError):
            current = None

    if current and current.get("products") == menu["products"] and current.get("categories") == menu["categories"]:
        print("Меню уже актуально")
        return

    menu["updatedAt"] = (current or {}).get("updatedAt") or menu["updatedAt"]
    if current and current.get("products") == menu["products"] and current.get("categories") == menu["categories"]:
        return

    with open(MENU_PATH, "w", encoding="utf-8") as handle:
        json.dump(menu, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(f"menu.json обновлён: {len(menu['products'])} позиций, {len(menu['categories'])} категорий")


if __name__ == "__main__":
    main()
