"""
Fortnite Item Shop collector.

Runs once a day. Asks the Fortnite-API what is in the shop today, saves the
raw response (so nothing is ever lost), and writes a tidy CSV with one row
per item-in-an-offer.

Run it by hand with:  python collect.py
"""

import csv
import gzip
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

SHOP_URL = "https://fortnite-api.com/v2/shop"
COSMETICS_URL = "https://fortnite-api.com/v2/cosmetics/br"

HERE = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(HERE, "data", "raw")
SHOP_DIR = os.path.join(HERE, "data", "shop")
COSMETICS_CSV = os.path.join(HERE, "data", "cosmetics.csv")

# One row per item per offer. Order matters - this is the CSV header.
SHOP_COLUMNS = [
    "shop_date",          # the day this snapshot is for (UTC)
    "offer_id",           # unique id for the offer (a "tile" in the shop)
    "dev_name",           # Epic's internal name for the offer
    "regular_price",      # list price in V-Bucks
    "final_price",        # what you actually pay
    "discount_vbucks",    # regular - final
    "discount_pct",       # discount as a share of list price
    "is_discounted",      # 1 if on sale, else 0
    "in_date",            # when this offer entered the shop
    "out_date",           # when it is scheduled to leave
    "giftable",
    "refundable",
    "sort_priority",      # higher = Epic pushed it harder (rough proxy for demand)
    "layout_id",          # which shop section it sat in
    "layout_name",
    "layout_rank",        # section ordering
    "layout_display_type",
    "tile_size",          # visual size of the tile (Size_1_x_1, etc)
    "offer_tag",
    "is_bundle",          # 1 if the offer is a bundle
    "bundle_name",
    "items_in_offer",     # how many items you get for the price
    "item_kind",          # br / track / car / instrument / lego
    "item_id",
    "item_name",
    "item_type",          # outfit, pickaxe, emote, ...
    "item_rarity",        # common, rare, legendary, icon series, ...
    "item_series",
    "item_set",
    "item_intro_chapter",
    "item_intro_season",
    "item_added",         # when the item first existed in the game
]


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "shop-tracker/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def val(obj, *keys):
    """Safely dig into nested dicts that may be missing or None."""
    for key in keys:
        if not isinstance(obj, dict):
            return ""
        obj = obj.get(key)
    return "" if obj is None else obj


def flatten_entry(entry, shop_date):
    """Turn one shop offer into one row per item inside it."""
    regular = entry.get("regularPrice") or 0
    final = entry.get("finalPrice") or 0
    discount = regular - final

    bundle = entry.get("bundle") or {}
    layout = entry.get("layout") or {}

    # An offer can contain several kinds of thing. Collect them all.
    item_groups = [
        ("br", entry.get("brItems") or []),
        ("track", entry.get("tracks") or []),
        ("car", entry.get("cars") or []),
        ("instrument", entry.get("instruments") or []),
        ("lego", entry.get("legoKits") or []),
    ]
    all_items = [(kind, item) for kind, items in item_groups for item in items]
    total_items = len(all_items)

    base = {
        "shop_date": shop_date,
        "offer_id": entry.get("offerId", ""),
        "dev_name": entry.get("devName", ""),
        "regular_price": regular,
        "final_price": final,
        "discount_vbucks": discount,
        "discount_pct": round(discount / regular, 4) if regular else "",
        "is_discounted": 1 if discount > 0 else 0,
        "in_date": entry.get("inDate", ""),
        "out_date": entry.get("outDate", ""),
        "giftable": int(bool(entry.get("giftable"))),
        "refundable": int(bool(entry.get("refundable"))),
        "sort_priority": entry.get("sortPriority", ""),
        "layout_id": layout.get("id", ""),
        "layout_name": layout.get("name", ""),
        "layout_rank": layout.get("rank", ""),
        "layout_display_type": layout.get("displayType", ""),
        "tile_size": entry.get("tileSize", ""),
        "offer_tag": val(entry.get("offerTag"), "text"),
        "is_bundle": 1 if bundle else 0,
        "bundle_name": bundle.get("name", "") if bundle else "",
        "items_in_offer": total_items,
    }

    if total_items == 0:
        # Offer with no resolvable items (rare). Keep it so the day's
        # revenue-side picture stays complete.
        row = dict(base)
        row.update({c: "" for c in SHOP_COLUMNS if c not in row})
        return [row]

    rows = []
    for kind, item in all_items:
        row = dict(base)
        row.update({
            "item_kind": kind,
            "item_id": item.get("id", ""),
            "item_name": item.get("title") or item.get("name", ""),
            "item_type": val(item, "type", "value"),
            "item_rarity": val(item, "rarity", "value"),
            "item_series": val(item, "series", "value"),
            "item_set": val(item, "set", "value"),
            "item_intro_chapter": val(item, "introduction", "chapter"),
            "item_intro_season": val(item, "introduction", "season"),
            "item_added": item.get("added", ""),
        })
        rows.append(row)
    return rows


def write_csv(path, columns, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def collect_shop():
    payload = fetch_json(SHOP_URL)
    data = payload["data"]
    shop_date = (data.get("date") or "")[:10] or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # 1. Save the raw response, compressed. Insurance: if you later realise
    #    you wanted a field you didn't save, it's still in here.
    raw_path = os.path.join(RAW_DIR, f"{shop_date}.json.gz")
    with gzip.open(raw_path, "wt", encoding="utf-8") as f:
        json.dump(payload, f)

    # 2. Save the tidy version you'll actually analyse.
    rows = []
    for entry in data.get("entries", []):
        rows.extend(flatten_entry(entry, shop_date))
    csv_path = os.path.join(SHOP_DIR, f"{shop_date}.csv")
    write_csv(csv_path, SHOP_COLUMNS, rows)

    print(f"{shop_date}: {len(data.get('entries', []))} offers -> {len(rows)} rows")
    return shop_date, len(rows)


COSMETICS_COLUMNS = [
    "item_id", "item_name", "item_type", "item_rarity", "item_series",
    "item_set", "item_intro_chapter", "item_intro_season", "item_added",
]


def collect_cosmetics():
    """The full catalogue of every cosmetic in the game.

    This is your lookup table: it tells you about items that are NOT in the
    shop today, which is what lets you ask 'what never comes back?'.
    Refreshed weekly - it changes slowly.
    """
    payload = fetch_json(COSMETICS_URL)
    rows = []
    for item in payload["data"]:
        rows.append({
            "item_id": item.get("id", ""),
            "item_name": item.get("name", ""),
            "item_type": val(item, "type", "value"),
            "item_rarity": val(item, "rarity", "value"),
            "item_series": val(item, "series", "value"),
            "item_set": val(item, "set", "value"),
            "item_intro_chapter": val(item, "introduction", "chapter"),
            "item_intro_season": val(item, "introduction", "season"),
            "item_added": item.get("added", ""),
        })
    write_csv(COSMETICS_CSV, COSMETICS_COLUMNS, rows)
    print(f"cosmetics catalogue: {len(rows)} items")


def main():
    os.makedirs(RAW_DIR, exist_ok=True)
    os.makedirs(SHOP_DIR, exist_ok=True)

    collect_shop()

    # Refresh the catalogue on Mondays, or if we've never fetched it.
    if datetime.now(timezone.utc).weekday() == 0 or not os.path.exists(COSMETICS_CSV):
        collect_cosmetics()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"collection failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
