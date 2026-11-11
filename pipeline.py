"""
Holiday Shelf — data pipeline (replaces the old pipeline.py AND pipeline_v2.py)
================================================================================
Fixes the item_id mismatch bug: view_item events used a different ID namespace
than add_to_cart/purchase events for the same product, which made the old
pipeline think most products had zero views. This version joins on item_name
(set at extraction time, in extract_corrected.sql) instead. Remaining spelling
differences between cart and purchase events are fixed in names.py.

Run: python pipeline.py
Reads from ./data/raw_events_v2.csv  (the output of extract_corrected.sql)
Writes to ./data/*.csv

Also prints an old-vs-new comparison against the existing ./data/product_summary.csv
(built by the earlier buggy pipeline) so tonight's "re-check every number" step has
something concrete to look at.
"""

import pandas as pd
import numpy as np
from pathlib import Path

from names import describe_name_map, load_name_map

DATA_DIR = Path(__file__).parent / "data"
RAW_PATH = DATA_DIR / "raw_events_v2.csv"
OLD_SUMMARY_PATH = DATA_DIR / "product_summary.csv"  # from the buggy pipeline, for comparison only

MIN_VIEWS_FLOOR = 100


def wilson_interval(successes, n, z=1.96):
    successes = np.asarray(successes, dtype=float)
    n = np.asarray(n, dtype=float)
    with np.errstate(divide="ignore", invalid="ignore"):
        p = np.where(n > 0, successes / n, 0.0)
        denom = 1 + z**2 / np.where(n > 0, n, 1)
        center = (p + z**2 / (2 * np.where(n > 0, n, 1))) / denom
        margin = (z * np.sqrt((p * (1 - p) + z**2 / (4 * np.where(n > 0, n, 1))) / np.where(n > 0, n, 1))) / denom
        low = np.where(n > 0, np.clip(center - margin, 0, 1), 0.0)
        high = np.where(n > 0, np.clip(center + margin, 0, 1), 0.0)
    return low, high


def build_canonical_category(df: pd.DataFrame) -> pd.DataFrame:
    """Same cleanup as before, but keyed on item_name now instead of item_id,
    since item_name is our new join key."""

    def most_common_nonnull(s: pd.Series):
        s = s.dropna()
        s = s[s != ""]
        if len(s) == 0:
            return None
        return s.mode().iloc[0]

    lookup = (
        df.groupby("item_name")
        .agg(item_category=("item_category_sample", most_common_nonnull))
        .reset_index()
    )
    lookup["item_category"] = lookup["item_category"].fillna("Uncategorized")
    return lookup


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH)
    df["event_date"] = pd.to_datetime(df["event_date"], format="%Y%m%d")
    # defensive, in case "(not set)" slipped through
    df = df[df["item_name"].notna() & (df["item_name"] != "(not set)")]
    df["item_name"] = df["item_name"].replace(load_name_map())
    return df


def build_product_summary(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("item_name", as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_added_to_cart=("sessions_added_to_cart", "sum"),
        sessions_checkout=("sessions_checkout", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        sessions_viewed_promo=("sessions_viewed_promo", "sum"),
        revenue=("revenue", "sum"),
    )
    agg = agg.merge(lookup, on="item_name", how="left")

    # Real view-based funnel now that views join correctly to purchases.
    agg["view_to_cart_rate"] = np.where(
        agg.sessions_viewed > 0, agg.sessions_added_to_cart / agg.sessions_viewed, np.nan
    )
    agg["cart_to_checkout_rate"] = np.where(
        agg.sessions_added_to_cart > 0, agg.sessions_checkout / agg.sessions_added_to_cart, np.nan
    )
    agg["checkout_to_buy_rate"] = np.where(
        agg.sessions_checkout > 0, agg.sessions_purchased / agg.sessions_checkout, np.nan
    )
    agg["view_to_buy_rate"] = np.where(
        agg.sessions_viewed > 0, agg.sessions_purchased / agg.sessions_viewed, np.nan
    )

    # Wilson CI on the real view-to-buy rate — this is now our primary rate,
    # replacing the old "exposure" (view+cart) proxy we used to paper over the bug.
    low, high = wilson_interval(agg["sessions_purchased"], agg["sessions_viewed"])
    agg["view_to_buy_ci_low"] = low
    agg["view_to_buy_ci_high"] = high

    # This should now be rare — only products where purchases still exceed views
    # (e.g. a real reorder, or someone buying without a logged view_item in this window).
    agg["views_likely_insufficient"] = agg["sessions_purchased"] > agg["sessions_viewed"]

    # Purchases missing under this name. The catalog's typical cart-to-purchase rate is
    # about 5%, so a product with 100+ cart sessions and ZERO purchases is not a real
    # 0% seller; its purchases are almost certainly logged under a different spelling
    # we have not matched. Its conversion rate is meaningless, so it must not be
    # labelled Window-Shopper or offered as something to replace.
    agg["purchases_unmatched"] = (agg["sessions_added_to_cart"] >= 100) & (agg["sessions_purchased"] == 0)

    eligible = agg[(agg.sessions_viewed >= MIN_VIEWS_FLOOR) & ~agg.purchases_unmatched].copy()
    median_views = eligible["sessions_viewed"].median()
    median_rate = eligible["view_to_buy_rate"].median()

    def label_row(row):
        if row["sessions_viewed"] < MIN_VIEWS_FLOOR or row["purchases_unmatched"]:
            return "Not Enough Data"
        high_views = row["sessions_viewed"] >= median_views
        high_rate = row["view_to_buy_rate"] > median_rate
        if high_views and high_rate:
            return "Star"
        if (not high_views) and high_rate:
            return "Hidden Gem"
        if high_views and not high_rate:
            return "Window-Shopper"
        return "Low Priority"

    agg["label"] = agg.apply(label_row, axis=1)
    agg["min_views_floor"] = MIN_VIEWS_FLOOR
    agg["median_views_used"] = median_views
    agg["median_rate_used"] = median_rate

    return agg.sort_values("revenue", ascending=False)


def build_weekly(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["week_start"] = df["event_date"] - pd.to_timedelta(df["event_date"].dt.weekday, unit="D")

    def phase(d):
        if d < pd.Timestamp("2020-11-27"):
            return "Early Nov"
        elif d < pd.Timestamp("2020-12-01"):
            return "Black Friday / Cyber Monday"
        elif d < pd.Timestamp("2020-12-26"):
            return "Mid-Dec"
        else:
            return "Post-Christmas"

    df["phase"] = df["week_start"].apply(phase)

    weekly = df.groupby(["item_name", "week_start", "phase"], as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        revenue=("revenue", "sum"),
    )
    weekly = weekly.merge(lookup, on="item_name", how="left")
    return weekly.sort_values(["week_start", "revenue"], ascending=[True, False])


def build_promo_check(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("item_name", as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        sessions_viewed_promo=("sessions_viewed_promo", "sum"),
    )
    agg = agg.merge(lookup, on="item_name", how="left")
    agg["view_to_buy_rate"] = np.where(
        agg.sessions_viewed > 0, agg.sessions_purchased / agg.sessions_viewed, np.nan
    )
    agg["had_promo_exposure"] = agg["sessions_viewed_promo"] > 0
    agg = agg[agg.sessions_viewed >= MIN_VIEWS_FLOOR]
    return agg


def build_country_device(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    """New in v2: country/device breakdown, kept for Person A's per-country phase
    dates and any later segmentation. Not used by Scorecard/Opportunity Finder yet."""
    agg = df.groupby(["item_name", "country", "device_category"], as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        revenue=("revenue", "sum"),
    )
    agg = agg.merge(lookup, on="item_name", how="left")
    return agg


def compare_old_vs_new(new_summary: pd.DataFrame, old: pd.DataFrame | None):
    if old is None or "exposure_likely_undercounted" not in old.columns:
        print("\n(No pre-fix product_summary.csv to compare against — skipping the old-vs-new diff.)")
        return

    print("\n" + "=" * 70)
    print("OLD vs NEW — key numbers to re-check before using in the app")
    print("=" * 70)

    old_flagged = int(old.get("exposure_likely_undercounted", pd.Series(dtype=bool)).sum())
    new_flagged = int(new_summary["views_likely_insufficient"].sum())
    print(f"'Undercounted' / insufficient-data flag:  OLD {old_flagged} products  ->  NEW {new_flagged} products")

    old_labels = old["label"].value_counts().to_dict() if "label" in old.columns else {}
    new_labels = new_summary["label"].value_counts().to_dict()
    print(f"\nQuadrant counts:")
    print(f"  OLD: {old_labels}")
    print(f"  NEW: {new_labels}")

    eligible_new = new_summary[
        (new_summary["sessions_viewed"] >= MIN_VIEWS_FLOOR)
        & (~new_summary["views_likely_insufficient"])
        & new_summary["view_to_buy_rate"].notna()
    ]
    med_rate = eligible_new["view_to_buy_rate"].median()
    med_views = eligible_new["sessions_viewed"].median()
    opportunities_new = eligible_new[
        (eligible_new["sessions_viewed"] < med_views) & (eligible_new["view_to_buy_rate"] > med_rate)
    ]
    print(f"\n'Opportunity' count (old pipeline reported 41):  NEW = {len(opportunities_new)}")
    print(f"Median eligible view-to-buy rate (old was 0.0%):  NEW = {med_rate:.1%}")
    print("=" * 70)


def main():
    if not RAW_PATH.exists():
        print(f"ERROR: {RAW_PATH} not found.")
        print("Run extract_corrected.sql in the BigQuery console first, download the")
        print(f"result, and save it as {RAW_PATH} before running this script.")
        return

    # IMPORTANT: snapshot the old product_summary.csv into memory BEFORE anything
    # below overwrites it. A previous version of this script read it for comparison
    # AFTER the overwrite, which meant it was silently comparing the new file against
    # itself. Load it once, right here, first.
    old_summary_snapshot = None
    if OLD_SUMMARY_PATH.exists():
        old_summary_snapshot = pd.read_csv(OLD_SUMMARY_PATH)

    name_map = describe_name_map()
    name_map.to_csv(DATA_DIR / "name_map_applied.csv", index=False)
    print(f"Name fixes applied: {len(name_map)} "
          f"({(name_map['origin'] == 'crosswalk (data)').sum()} from the crosswalk, "
          f"{(name_map['origin'] == 'manual alias').sum()} manual) -> data/name_map_applied.csv")

    print("Loading corrected raw export...")
    df = load_raw()
    print(f"  {len(df):,} rows, {df['item_name'].nunique():,} distinct products (by name)")

    print("Building canonical item_name -> category lookup...")
    lookup = build_canonical_category(df)

    print("Building product_summary.csv...")
    product_summary = build_product_summary(df, lookup)
    product_summary.to_csv(DATA_DIR / "product_summary.csv", index=False)
    print(f"  {len(product_summary):,} products written")
    print(f"  label counts:\n{product_summary['label'].value_counts()}")

    print("\nBuilding weekly.csv (Season Playbook)...")
    weekly = build_weekly(df, lookup)
    weekly.to_csv(DATA_DIR / "weekly.csv", index=False)
    print(f"  {len(weekly):,} product-week rows written")

    print("\nBuilding promo_check.csv...")
    promo = build_promo_check(df, lookup)
    promo.to_csv(DATA_DIR / "promo_check.csv", index=False)
    print(f"  {len(promo):,} products with enough views written")

    print("\nBuilding country_device.csv (new — for Person A's per-country phases)...")
    country_device = build_country_device(df, lookup)
    country_device.to_csv(DATA_DIR / "country_device.csv", index=False)
    print(f"  {len(country_device):,} product x country x device rows written")

    compare_old_vs_new(product_summary, old_summary_snapshot)

    print("\nDone. product_summary.csv / weekly.csv / promo_check.csv have been")
    print("overwritten with corrected data. The old files are no longer used by app.py.")


if __name__ == "__main__":
    main()