"""
First look at the shop data.

Run this once you have at least a couple of weeks of days collected:

    pip install -r requirements.txt
    python analysis/01_first_look.py

It does three things:
  1. Loads every daily CSV into one table and adds a few useful columns.
  2. Prints some basic facts so you can sanity-check the data.
  3. Runs the price regression - the STAT 301 part.
"""

import glob
import os

import pandas as pd
import statsmodels.formula.api as smf

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SHOP_GLOB = os.path.join(ROOT, "data", "shop", "*.csv")


# ---------------------------------------------------------------- load

def load_panel():
    """Stack every daily file into one long table."""
    files = sorted(glob.glob(SHOP_GLOB))
    if not files:
        raise SystemExit("No data yet. Run `python collect.py` first.")

    df = pd.concat((pd.read_csv(f) for f in files), ignore_index=True)
    df["shop_date"] = pd.to_datetime(df["shop_date"])
    df["item_added"] = pd.to_datetime(df["item_added"], format="mixed", utc=True, errors="coerce")

    # How old was the item, in days, on the day it was being sold?
    # This is the single most useful derived column you have.
    df["item_age_days"] = (
        df["shop_date"].dt.tz_localize("UTC") - df["item_added"]
    ).dt.days

    # Price per item: a 2800 bundle of 4 things isn't a 2800 skin.
    df["price_per_item"] = df["final_price"] / df["items_in_offer"].clip(lower=1)

    return df


def add_rotation_features(df):
    """For each item: how many times has it shown up, and how long was
    the gap since the last time?  This is the scarcity question."""
    df = df.sort_values(["item_id", "shop_date"])
    grp = df.groupby("item_id")["shop_date"]
    df["appearance_number"] = grp.rank(method="dense")
    df["days_since_last_seen"] = grp.diff().dt.days
    return df


# ------------------------------------------------------------- describe

def describe(df):
    days = df["shop_date"].nunique()
    print(f"\n{'='*60}\nDATA SO FAR\n{'='*60}")
    print(f"Days collected      : {days}")
    print(f"Date range          : {df.shop_date.min().date()} to {df.shop_date.max().date()}")
    print(f"Rows (item-days)    : {len(df):,}")
    print(f"Distinct items seen : {df.item_id.nunique():,}")
    print(f"Share on sale       : {df.is_discounted.mean():.1%}")

    print("\nItems in the shop, by rarity:")
    print(df["item_rarity"].value_counts().head(10).to_string())

    print("\nAverage price per item, by rarity (outfits only):")
    outfits = df[df.item_type == "outfit"]
    if len(outfits):
        print(outfits.groupby("item_rarity")["price_per_item"]
                .agg(["mean", "median", "count"])
                .sort_values("mean", ascending=False)
                .round(0).to_string())


# ------------------------------------------------------------ regression

def price_model(df):
    """Q1: what drives the list price of an outfit?

    We use only outfits sold on their own, so we're comparing like with
    like - bundles and pickaxes follow different pricing rules.
    """
    d = df[(df.item_type == "outfit") &
           (df.is_bundle == 0) &
           (df.items_in_offer == 1)].copy()

    # One row per item, not per item-day. Otherwise an item that sat in
    # the shop for 7 days would count seven times and fake our sample size.
    d = d.drop_duplicates(subset="item_id")
    d = d.dropna(subset=["regular_price", "item_rarity", "item_age_days"])

    if len(d) < 30:
        print("\nNot enough single outfits yet for a regression "
              f"({len(d)} so far). Collect more days.")
        return

    # Keep rarities with enough observations to mean anything.
    keep = d["item_rarity"].value_counts()
    d = d[d["item_rarity"].isin(keep[keep >= 5].index)]

    d["age_years"] = d["item_age_days"] / 365.0

    print(f"\n{'='*60}\nQ1: WHAT DRIVES OUTFIT PRICE?  (n={len(d)})\n{'='*60}")
    model = smf.ols("regular_price ~ C(item_rarity) + age_years", data=d).fit()
    print(model.summary().tables[1])
    print(f"\nR-squared: {model.rsquared:.3f}")
    print("Read this as: holding rarity constant, each extra year of age is")
    print(f"worth {model.params.get('age_years', float('nan')):+.0f} V-Bucks on the list price.")


def discount_model(df):
    """Q2: which items get marked down?"""
    d = df[(df.is_bundle == 0) & (df.items_in_offer == 1)].copy()
    d = d.drop_duplicates(subset=["item_id", "shop_date"])
    d = d.dropna(subset=["item_age_days", "item_rarity"])

    if len(d) < 100 or d["is_discounted"].nunique() < 2:
        print("\nNot enough variation yet to model discounts. Collect more days.")
        return

    d["age_years"] = d["item_age_days"] / 365.0
    print(f"\n{'='*60}\nQ2: WHAT GETS DISCOUNTED?  (n={len(d)})\n{'='*60}")
    model = smf.logit("is_discounted ~ age_years + C(item_type)", data=d).fit(disp=False)
    print(model.summary().tables[1])


def rotation_summary(df):
    """Q3: how long do items stay away between appearances?"""
    gaps = df.dropna(subset=["days_since_last_seen"])
    gaps = gaps[gaps.days_since_last_seen > 1]   # ignore consecutive days
    if gaps.empty:
        print("\nNo return visits recorded yet - this one needs months, not days.")
        return
    print(f"\n{'='*60}\nQ3: TIME BETWEEN SHOP APPEARANCES\n{'='*60}")
    print(gaps["days_since_last_seen"].describe().round(1).to_string())
    print("\nLongest waits before returning:")
    print(gaps.nlargest(10, "days_since_last_seen")[
        ["item_name", "item_rarity", "days_since_last_seen"]].to_string(index=False))


if __name__ == "__main__":
    panel = add_rotation_features(load_panel())
    describe(panel)
    price_model(panel)
    discount_model(panel)
    rotation_summary(panel)
    print("\nDone.\n")
