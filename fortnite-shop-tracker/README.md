# Fortnite Item Shop Tracker

A daily record of the Fortnite item shop, and an analysis of how it is priced.

The Fortnite API tells you what is in the shop **today**. It does not tell you
what was in the shop last week. So this repo asks the API once a day, every
day, and saves the answer. After a few months that adds up to a dataset that
does not otherwise exist publicly.

## Why bother

Three questions this data can answer:

1. **What drives price?** Does rarity explain what an outfit costs? Do older
   items get cheaper?
2. **What gets discounted?** Which items go on sale, and what do they have in
   common?
3. **How does rotation work?** When an item leaves the shop, how long until it
   comes back — and does the wait depend on how desirable the item is?

The honest limitation: this data has **no sales figures**. You can never see
how many people bought something, so you cannot measure demand directly. The
closest proxy is `sort_priority` and shop placement, which reflect Epic's own
beliefs about what will sell. Say so in any writeup.

## Setup (about ten minutes, once)

1. Create a new **public** repo on GitHub and push these files to it.
2. Go to **Settings → Actions → General → Workflow permissions** and select
   **Read and write permissions**. Without this the daily job cannot save data.
3. Go to the **Actions** tab, pick "Collect daily shop", and click
   **Run workflow** to test it now instead of waiting until midnight.
4. Check that a file appeared in `data/shop/`. If it did, you are done — it
   will run itself every day from here on.

To run it on your own machine instead:

```bash
python collect.py
```

No packages needed for collection; it uses only the Python standard library.

## Analysis

```bash
pip install -r requirements.txt
python analysis/01_first_look.py
```

Wait until you have two or three weeks of data before expecting much. Question
3 needs a couple of months.

## What's in the data

`data/shop/YYYY-MM-DD.csv` — one row per **item per offer**. A bundle of four
items on one day is four rows, all sharing an `offer_id` and a price. Remember
to de-duplicate before running a regression, or long-running offers will be
counted once per day and inflate your sample size.

| Column | What it is |
| --- | --- |
| `shop_date` | The day this snapshot covers (UTC) |
| `offer_id` | Unique id for the offer — the tile you click in the shop |
| `regular_price` / `final_price` | List price and actual price, in V-Bucks |
| `discount_vbucks` / `discount_pct` / `is_discounted` | Derived from the two prices |
| `in_date` / `out_date` | When the offer entered and is due to leave |
| `sort_priority` | How high Epic placed it. Rough proxy for expected demand |
| `layout_id` / `layout_name` / `layout_rank` | Which section of the shop it sat in |
| `tile_size` | How much screen real estate it got |
| `is_bundle` / `bundle_name` / `items_in_offer` | Bundle structure |
| `item_kind` | `br`, `track`, `car`, `instrument`, `lego` |
| `item_id` / `item_name` / `item_type` | The item itself |
| `item_rarity` / `item_series` / `item_set` | Rarity tier, series, and set membership |
| `item_intro_chapter` / `item_intro_season` | When it was introduced |
| `item_added` | When it first existed in the game — gives you item age |

`data/cosmetics.csv` — the full catalogue of every cosmetic in the game
(~16,000 items), refreshed weekly. This is your lookup table. It matters
because it includes items that are **not** in the shop, which is what lets you
ask which items never come back.

`data/raw/YYYY-MM-DD.json.gz` — the untouched API response. If you later
realise you wanted a field the CSV drops, it is still in here.

## Layout

```
collect.py                    the daily collector
.github/workflows/collect.yml the schedule that runs it
analysis/01_first_look.py     loads the data, runs the models
tests/sample_shop.json        a small fixture for testing the parser
data/                         everything collected so far
```

## Data source

[fortnite-api.com](https://fortnite-api.com) — free, no key required.
Unofficial and not endorsed by Epic Games.
