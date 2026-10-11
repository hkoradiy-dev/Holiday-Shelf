"""
Holiday Shelf — data pipeline
Takes the raw BigQuery export (one row per item_id per event_date) and produces:
  - product_summary.csv   : one row per product, full-period metrics, Wilson CI, quadrant label
  - weekly.csv             : one row per product per ISO week, for the Season Playbook
  - promo_check.csv        : promo-exposed vs non-promo-exposed conversion comparison

Run: python pipeline.py
Reads from ./data/raw_events.csv
Writes to ./data/*.csv
"""

import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
RAW_PATH = DATA_DIR / "raw_events.csv"

MIN_VIEWS_FLOOR = 100  # below this, a product is "Not Enough Data" regardless of its rate


def wilson_interval(successes, n, z=1.96):
    """Wilson score interval for a binomial proportion. Returns (low, high).
    Safe for n=0 (returns (0,0))."""
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


def build_canonical_lookup(df: pd.DataFrame) -> pd.DataFrame:
    """For each item_id, pick the most frequent non-null item_name and item_category.
    Raw data has the same item_id appearing with different category breadcrumbs
    and occasional HTML-entity differences in name across rows — this collapses
    that back down to one canonical identity per product."""

    def most_common_nonnull(s: pd.Series):
        s = s.dropna()
        s = s[s != ""]
        if len(s) == 0:
            return None
        return s.mode().iloc[0]

    lookup = (
        df.groupby("item_id")
        .agg(
            item_name=("item_name", most_common_nonnull),
            item_category=("item_category", most_common_nonnull),
        )
        .reset_index()
    )
    lookup["item_category"] = lookup["item_category"].fillna("Uncategorized")
    lookup["item_name"] = lookup["item_name"].fillna("Unknown item")
    return lookup


def load_raw() -> pd.DataFrame:
    df = pd.read_csv(RAW_PATH, dtype={"item_id": str})
    df["event_date"] = pd.to_datetime(df["event_date"], format="%Y%m%d")
    return df


def build_product_summary(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("item_id", as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_added_to_cart=("sessions_added_to_cart", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        sessions_viewed_promo=("sessions_viewed_promo", "sum"),
        revenue=("revenue", "sum"),
    )
    agg = agg.merge(lookup, on="item_id", how="left")

    # IMPORTANT: raw_view_item_events undercounts real exposure for this dataset —
    # confirmed via a direct BigQuery diagnostic that many high-purchase products
    # (gift cards, and ordinary merch like backpacks) have ZERO view_item events
    # but healthy add_to_cart and purchase counts. This means shoppers reach many
    # products via listing pages / quick-add without ever loading a product detail
    # page. Using sessions_viewed alone as "visibility" would silently exclude the
    # majority of real purchase volume from the Scorecard.
    #
    # Fix: define exposure as sessions that EITHER viewed OR added to cart. This is
    # an approximation — a session that did both is counted once in each raw column,
    # so summing them is an upper bound, not an exact distinct-session count. A fully
    # exact version would require a session-level UNION DISTINCT re-query in BigQuery.
    agg["sessions_exposed"] = agg["sessions_viewed"] + agg["sessions_added_to_cart"]

    # funnel rates — view_to_cart/cart_to_buy still use view_item where it exists,
    # but the HEADLINE metric for the Scorecard is exposure_to_buy_rate, not view_to_buy_rate
    agg["view_to_cart_rate"] = np.where(
        agg.sessions_viewed > 0, agg.sessions_added_to_cart / agg.sessions_viewed, np.nan
    )
    agg["cart_to_buy_rate"] = np.where(
        agg.sessions_added_to_cart > 0, agg.sessions_purchased / agg.sessions_added_to_cart, np.nan
    )
    agg["exposure_to_buy_rate"] = np.where(
        agg.sessions_exposed > 0, agg.sessions_purchased / agg.sessions_exposed, np.nan
    )
    # keep the old view-only rate too, for transparency / comparison in the app
    agg["view_only_to_buy_rate"] = np.where(
        agg.sessions_viewed > 0, agg.sessions_purchased / agg.sessions_viewed, np.nan
    )

    # Wilson CI on exposure-to-buy rate (the metric the Scorecard y-axis now uses)
    low, high = wilson_interval(agg["sessions_purchased"], agg["sessions_exposed"])
    agg["exposure_to_buy_ci_low"] = low
    agg["exposure_to_buy_ci_high"] = high

    # labeling: quadrants based on median split among products that clear the exposure floor
    eligible = agg[agg.sessions_exposed >= MIN_VIEWS_FLOOR].copy()
    median_exposure = eligible["sessions_exposed"].median()
    median_rate = eligible["exposure_to_buy_rate"].median()

    def label_row(row):
        if row["sessions_exposed"] < MIN_VIEWS_FLOOR:
            return "Not Enough Data"
        high_exposure = row["sessions_exposed"] >= median_exposure
        # STRICT > not >=: this dataset is zero-inflated (90% of eligible products
        # have exactly 0 purchases), so median_rate is often 0.0. Using >= would make
        # "rate >= 0" true for every product and collapse Window-Shopper/Low Priority
        # out of existence. Strict > means "high rate" requires at least one purchase
        # when the median is 0.
        high_rate = row["exposure_to_buy_rate"] > median_rate
        if high_exposure and high_rate:
            return "Star"
        if (not high_exposure) and high_rate:
            return "Hidden Gem"
        if high_exposure and not high_rate:
            return "Window-Shopper"
        return "Low Priority"

    agg["label"] = agg.apply(label_row, axis=1)
    agg["min_views_floor"] = MIN_VIEWS_FLOOR
    agg["median_exposure_used"] = median_exposure
    agg["median_rate_used"] = median_rate

    # Flag products where purchases exceed exposure — proof that even view+cart
    # doesn't fully capture how shoppers reached this product (e.g. reorders,
    # "buy again" flows). Their rate is mathematically >100% and should never be
    # displayed as a trustworthy percentage without this caveat attached.
    agg["exposure_likely_undercounted"] = agg["sessions_purchased"] > agg["sessions_exposed"]

    return agg.sort_values("revenue", ascending=False)


def build_weekly(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["iso_year"] = df["event_date"].dt.isocalendar().year
    df["iso_week"] = df["event_date"].dt.isocalendar().week
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

    weekly = df.groupby(["item_id", "week_start", "phase"], as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        revenue=("revenue", "sum"),
    )
    weekly = weekly.merge(lookup, on="item_id", how="left")
    return weekly.sort_values(["week_start", "revenue"], ascending=[True, False])


def build_promo_check(df: pd.DataFrame, lookup: pd.DataFrame) -> pd.DataFrame:
    agg = df.groupby("item_id", as_index=False).agg(
        sessions_viewed=("sessions_viewed", "sum"),
        sessions_added_to_cart=("sessions_added_to_cart", "sum"),
        sessions_purchased=("sessions_purchased", "sum"),
        sessions_viewed_promo=("sessions_viewed_promo", "sum"),
    )
    agg = agg.merge(lookup, on="item_id", how="left")
    agg["sessions_exposed"] = agg["sessions_viewed"] + agg["sessions_added_to_cart"]
    agg["exposure_to_buy_rate"] = np.where(
        agg.sessions_exposed > 0, agg.sessions_purchased / agg.sessions_exposed, np.nan
    )
    agg["had_promo_exposure"] = agg["sessions_viewed_promo"] > 0
    # keep only products with enough exposure to say anything about their rate
    agg = agg[agg.sessions_exposed >= MIN_VIEWS_FLOOR]
    return agg


def main():
    print("Loading raw export...")
    df = load_raw()
    print(f"  {len(df):,} rows, {df['item_id'].nunique():,} distinct item_ids")

    print("Building canonical item_id -> name/category lookup...")
    lookup = build_canonical_lookup(df)

    print("Building product_summary.csv...")
    product_summary = build_product_summary(df, lookup)
    product_summary.to_csv(DATA_DIR / "product_summary.csv", index=False)
    print(f"  {len(product_summary):,} products written")
    print(f"  label counts:\n{product_summary['label'].value_counts()}")

    print("Building weekly.csv (Season Playbook)...")
    weekly = build_weekly(df, lookup)
    weekly.to_csv(DATA_DIR / "weekly.csv", index=False)
    print(f"  {len(weekly):,} product-week rows written")

    print("Building promo_check.csv...")
    promo = build_promo_check(df, lookup)
    promo.to_csv(DATA_DIR / "promo_check.csv", index=False)
    print(f"  {len(promo):,} products with enough views written")

    print("Done.")


if __name__ == "__main__":
    main()
