"""
Holiday Shelf: Bundles & Cart Rescue data builder (B3)

Run:  python build_bundles.py
Reads:  data/orders_v2.csv        (from extract_bundles.sql: one row per order x product)
        data/product_summary.csv  (from pipeline.py)
Writes: data/bundle_pairs.csv     (bought-together pairs with strength metrics)
        data/cart_rescue.csv      (products added to cart often but rarely bought)

Everything is keyed on item_name, the same key as product_summary.csv.
"""

import itertools
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd

from names import load_name_map

DATA_DIR = Path(__file__).parent / "data"

MIN_PAIR_ORDERS = 5      # pairs seen in fewer orders than this are dropped (2-order flukes)
MIN_CART_SESSIONS = 100  # Cart Rescue needs enough carts to say anything

COLOR_WORDS = {
    "blue", "red", "green", "yellow", "black", "white", "grey", "gray", "navy", "mint",
    "orange", "pink", "purple", "charcoal", "heathered", "multicolor", "multicolored",
    "ivory", "indigo", "lime", "teal", "brown", "tan", "khaki",
}


def _tokens(name: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", name.lower())


def family_key(name: str) -> str:
    """Name with colour words removed, so 'Light Pen Blue' and 'Light Pen Red' match."""
    return " ".join(t for t in _tokens(name) if t not in COLOR_WORDS)


def same_family(a: str, b: str) -> bool:
    """Heuristic: two products are variants of one another (a different colour, size or
    campus of the same item) when, ignoring colour words, either
      - their names are identical ('Light Pen Blue' / 'Light Pen Red'), or
      - they have the same number of words (4 or more), the same last word (the product
        type), and differ in exactly one other word ('Kirkland Campus Sticker' /
        'Bellevue Campus Sticker', 'Large Trace Journal' / 'Small Trace Journal').
    It is deliberately strict so it does not hide real cross-sells such as 'PNW Campus
    Mug' + 'PNW Campus Lapel Pin'. It can miss some variants; the page lets you show them."""
    ta = [t for t in _tokens(a) if t not in COLOR_WORDS]
    tb = [t for t in _tokens(b) if t not in COLOR_WORDS]
    if ta == tb:
        return True
    if len(ta) == len(tb) and len(ta) >= 4 and ta[-1] == tb[-1]:
        return sum(x != y for x, y in zip(ta, tb)) == 1
    return False


def build_pairs(orders: pd.DataFrame) -> pd.DataFrame:
    n_orders = orders["transaction_id"].nunique()
    baskets = orders.groupby("transaction_id")["item_name"].apply(lambda s: sorted(set(s)))

    item_orders = Counter()
    pair_orders = Counter()
    for basket in baskets:
        item_orders.update(basket)
        pair_orders.update(itertools.combinations(basket, 2))

    price = orders.groupby("item_name")["price"].median()
    category = orders.groupby("item_name")["item_category"].agg(
        lambda s: s.dropna().mode().iloc[0] if s.notna().any() else "Uncategorized"
    )

    rows = []
    for (a, b), together in pair_orders.items():
        if together < MIN_PAIR_ORDERS:
            continue
        # Anchor = the pricier product, add-on = the cheaper one. Ties: alphabetical.
        if (price[a], a) >= (price[b], b):
            anchor, addon = a, b
        else:
            anchor, addon = b, a
        lift = together * n_orders / (item_orders[a] * item_orders[b])
        rows.append(
            {
                "anchor": anchor,
                "addon": addon,
                "anchor_category": category[anchor],
                "addon_category": category[addon],
                "anchor_price": price[anchor],
                "addon_price": price[addon],
                "orders_together": together,
                "anchor_orders": item_orders[anchor],
                "addon_orders": item_orders[addon],
                # of all orders containing the anchor, share that also had the add-on
                "addon_attach_rate": together / item_orders[anchor],
                "lift": lift,
                "same_family": same_family(anchor, addon),
            }
        )
    out = pd.DataFrame(rows)
    out["price_ratio"] = out["anchor_price"] / out["addon_price"].where(out["addon_price"] > 0)
    # Sorted by evidence (orders together). Lift is kept as a column, but it rewards rare
    # items: sorted by lift, $1 sticker pairs seen 5 times would sit at the top.
    return out.sort_values(["orders_together", "lift"], ascending=False).reset_index(drop=True)


def build_cart_rescue(summary: pd.DataFrame, orders: pd.DataFrame) -> pd.DataFrame:
    price = orders.groupby("item_name")["price"].median().rename("typical_price")
    df = summary.merge(price, on="item_name", how="left")
    # Products whose purchases are logged under a different spelling would look like
    # "all carts, no purchases" and dominate this list, so they are left out.
    df = df[~df["purchases_unmatched"]]
    df = df[df["sessions_added_to_cart"] >= MIN_CART_SESSIONS].copy()
    df["cart_to_buy_rate"] = df["sessions_purchased"] / df["sessions_added_to_cart"]
    df["abandoned_carts"] = (df["sessions_added_to_cart"] - df["sessions_purchased"]).clip(lower=0)
    median_rate = df["cart_to_buy_rate"].median()
    rescue = df[df["cart_to_buy_rate"] < median_rate].copy()
    rescue["catalog_median_cart_to_buy"] = median_rate
    cols = [
        "item_name", "item_category", "typical_price", "sessions_added_to_cart",
        "sessions_checkout", "sessions_purchased", "cart_to_buy_rate", "abandoned_carts",
        "catalog_median_cart_to_buy", "label",
    ]
    return rescue[cols].sort_values("abandoned_carts", ascending=False).reset_index(drop=True)


def main():
    orders_path = DATA_DIR / "orders_v2.csv"
    if not orders_path.exists():
        print(f"ERROR: {orders_path} not found. Run extract_bundles.sql in BigQuery first.")
        return
    orders = pd.read_csv(orders_path)
    # Same spelling fixes the pipeline applies (names.py), so order names line up
    # with the names on the Scorecard.
    orders["item_name"] = orders["item_name"].replace(load_name_map())
    summary = pd.read_csv(DATA_DIR / "product_summary.csv")

    n_orders = orders["transaction_id"].nunique()
    per_order = orders.groupby("transaction_id").size()
    print(f"{n_orders:,} orders, {len(orders):,} order lines, "
          f"{per_order.mean():.2f} products per order, "
          f"{(per_order >= 2).sum():,} orders with 2+ products")

    pairs = build_pairs(orders)
    pairs.to_csv(DATA_DIR / "bundle_pairs.csv", index=False)
    print(f"\nbundle_pairs.csv: {len(pairs):,} pairs seen in >= {MIN_PAIR_ORDERS} orders "
          f"({int(pairs['same_family'].sum()):,} are colour/size variants, "
          f"{int((~pairs['same_family']).sum()):,} are cross-product)")

    rescue = build_cart_rescue(summary, orders)
    rescue.to_csv(DATA_DIR / "cart_rescue.csv", index=False)
    print(f"cart_rescue.csv: {len(rescue):,} products with >= {MIN_CART_SESSIONS} cart sessions "
          f"and a below-median cart-to-purchase rate "
          f"(median = {rescue['catalog_median_cart_to_buy'].iloc[0]:.1%})")


if __name__ == "__main__":
    main()