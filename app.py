

import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title="Holiday Shelf", layout="wide")


@st.cache_data
def load_product_summary():
    return pd.read_csv(DATA_DIR / "product_summary.csv")


@st.cache_data
def load_weekly():
    return pd.read_csv(DATA_DIR / "weekly.csv", parse_dates=["week_start"])


@st.cache_data
def load_promo_check():
    return pd.read_csv(DATA_DIR / "promo_check.csv")


if "shortlist" not in st.session_state:
    st.session_state.shortlist = {}  # item_name -> row dict


def add_to_shortlist(row: dict):
    st.session_state.shortlist[row["item_name"]] = row


def remove_from_shortlist(item_name: str):
    st.session_state.shortlist.pop(item_name, None)


st.sidebar.title("Holiday Shelf")
page = st.sidebar.radio(
    "Go to",
    ["Shelf Scorecard", "Opportunity Finder", "Promo Check", "Season Playbook", "Shortlist Builder"],
)

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Shortlist: {len(st.session_state.shortlist)} products**")
if st.session_state.shortlist:
    with st.sidebar.expander("View shortlist"):
        for name in list(st.session_state.shortlist.keys()):
            c1, c2 = st.columns([4, 1])
            c1.caption(name)
            if c2.button("✕", key=f"remove_{name}"):
                remove_from_shortlist(name)
                st.rerun()

LABEL_COLORS = {
    "Star": "#2ecc71",
    "Hidden Gem": "#9b59b6",
    "Window-Shopper": "#e67e22",
    "Low Priority": "#95a5a6",
    "Not Enough Data": "#bdc3c7",
}

# ---------------------------------------------------------------------------
# SHELF SCORECARD
# ---------------------------------------------------------------------------
if page == "Shelf Scorecard":
    st.title("Shelf Scorecard")
    st.caption(
        "Each bubble is a product. X-axis: sessions that viewed the product (log scale — "
        "traffic varies by orders of magnitude, so a linear axis crams almost every product "
        "into one corner). Y-axis: share of those viewing sessions that converted to a "
        "purchase. Bubble size: revenue. Color: quadrant label."
    )

    df = load_product_summary()

    with st.expander("⚠️ Known data limitations — read before trusting this chart", expanded=False):
        n_flagged = int(df["views_likely_insufficient"].sum())
        st.markdown(
            f"""
- **Products are now matched by name, not by GA4's item_id.** We found that `view_item`
  events and `add_to_cart`/`purchase` events use two different ID systems for the same
  product. Joining by ID made it look like ~49% of products had zero views; joining by
  name instead drops that to {n_flagged} of {len(df)} products ({n_flagged/len(df):.1%}).
- **{n_flagged} products still show purchases exceeding their view count** — these are
  flagged `views_likely_insufficient` and should be read cautiously; everything else now
  uses real, trustworthy view counts.
- **Minimum view floor is {int(df['min_views_floor'].iloc[0])} sessions.** Below that, a
  product is labeled "Not Enough Data" regardless of its rate.
- **This is one historical holiday season (Nov 2020 – Jan 2021).** Quadrant placement is a
  starting hypothesis to test this year, not a guarantee.
            """
        )

    categories = sorted(df["item_category"].dropna().unique().tolist())
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        selected_categories = st.multiselect("Category", categories, default=[])
    with col2:
        min_views = st.number_input("Minimum sessions viewed", min_value=0, value=0, step=50)
    with col3:
        hide_flagged = st.checkbox("Hide insufficient-view products", value=False)
    show_labels = st.multiselect(
        "Show quadrants",
        ["Star", "Hidden Gem", "Window-Shopper", "Low Priority", "Not Enough Data"],
        default=["Star", "Hidden Gem", "Window-Shopper", "Low Priority"],
    )

    plot_df = df.copy()
    if selected_categories:
        plot_df = plot_df[plot_df["item_category"].isin(selected_categories)]
    if min_views > 0:
        plot_df = plot_df[plot_df["sessions_viewed"] >= min_views]
    if hide_flagged:
        plot_df = plot_df[~plot_df["views_likely_insufficient"]]
    plot_df = plot_df[plot_df["label"].isin(show_labels)]

    # Log scale needs a strictly positive x; a product with 0 views can't sit on a log
    # axis, so give it a 1-session floor for display only (doesn't affect the real data).
    plot_df["display_views"] = plot_df["sessions_viewed"].clip(lower=1)
    # Still guard the rare >100% case for display, without hiding it from the table.
    plot_df["display_rate"] = plot_df["view_to_buy_rate"].clip(upper=1.0)

    if len(plot_df) == 0:
        st.warning("No products match the current filters.")
    else:
        fig = px.scatter(
            plot_df,
            x="display_views",
            y="display_rate",
            size="revenue",
            color="label",
            color_discrete_map=LABEL_COLORS,
            log_x=True,
            hover_name="item_name",
            hover_data={
                "item_category": True,
                "sessions_viewed": True,
                "sessions_purchased": True,
                "revenue": ":$.0f",
                "views_likely_insufficient": True,
                "display_views": False,
                "display_rate": False,
            },
            size_max=45,
            labels={
                "display_views": "Sessions Viewed (log scale)",
                "display_rate": "View → Purchase rate",
            },
        )
        fig.update_layout(height=600, legend_title_text="Quadrant")
        st.plotly_chart(fig, use_container_width=True)

        n_flagged_shown = int(plot_df["views_likely_insufficient"].sum())
        st.caption(
            f"Showing {len(plot_df):,} of {len(df):,} products. "
            f"{n_flagged_shown} shown here have insufficient view data."
        )

    st.markdown("### Add products to your shortlist")
    pick_df = plot_df.sort_values("revenue", ascending=False).head(30)
    for _, row in pick_df.iterrows():
        c1, c2, c3, c4, c5 = st.columns([3, 1.3, 1.3, 1.3, 1])
        c1.write(row["item_name"])
        c2.write(f"{row['sessions_viewed']:,} views")
        c3.write(f"{row['view_to_buy_rate']:.1%} rate")
        c4.write(row["label"])
        key = f"add_scorecard_{row['item_name']}"
        if row["item_name"] in st.session_state.shortlist:
            c5.button("✓ Added", key=key, disabled=True)
        else:
            if c5.button("+ Add", key=key):
                add_to_shortlist(row.to_dict())
                st.rerun()

    with st.expander("View full table"):
        st.dataframe(
            plot_df[
                [
                    "item_name", "item_category", "sessions_viewed", "sessions_purchased",
                    "view_to_buy_rate", "view_to_buy_ci_low", "view_to_buy_ci_high",
                    "revenue", "label", "views_likely_insufficient",
                ]
            ].sort_values("revenue", ascending=False),
            use_container_width=True,
        )

# ---------------------------------------------------------------------------
# OPPORTUNITY FINDER — PHASE 2
# ---------------------------------------------------------------------------
elif page == "Opportunity Finder":
    st.title("Opportunity Finder")
    st.caption(
        "Products worth featuring: ranked by the cautious (lower-bound) end of their "
        "confidence interval — 'we're fairly confident at least X% of viewers buy' — "
        "not a single point estimate that could be a lucky fluke."
    )

    df = load_product_summary().copy()

    eligible = df[
        (df["sessions_viewed"] >= int(df["min_views_floor"].iloc[0]))
        & (~df["views_likely_insufficient"].astype(bool))
        & df["view_to_buy_rate"].notna()
    ].copy()

    if eligible.empty:
        st.warning("No products meet the current data-quality rules.")
    else:
        median_views = float(eligible["sessions_viewed"].median())
        median_rate = float(eligible["view_to_buy_rate"].median())

        opportunities = eligible[
            (eligible["sessions_viewed"] < median_views)
            & (eligible["view_to_buy_rate"] > median_rate)
        ].copy()

        if opportunities.empty:
            st.info("No products currently meet the Opportunity criteria.")
        else:
            # Rank by the CONSERVATIVE end of the confidence interval, not a made-up
            # score. "At least X% of viewers buy, even in the worst plausible case"
            # is a number the merchandiser can actually defend in a room.
            opportunities = opportunities.sort_values(
                ["view_to_buy_ci_low", "revenue"], ascending=False
            )

            # Pair each opportunity with the weakest same-category product it could
            # replace: a Window-Shopper or Low Priority item in the same category
            # with the lowest conversion rate, so the suggestion is concrete, not
            # just "this is good" with no action attached.
            replace_candidates = df[df["label"].isin(["Window-Shopper", "Low Priority"])]

            def find_replacement(category):
                same_cat = replace_candidates[replace_candidates["item_category"] == category]
                if same_cat.empty:
                    return None
                weakest = same_cat.sort_values("view_to_buy_rate", ascending=True).iloc[0]
                return weakest["item_name"]

            opportunities["replaces"] = opportunities["item_category"].apply(find_replacement)

            c1, c2, c3 = st.columns(3)
            c1.metric("Qualified opportunities", f"{len(opportunities):,}")
            c2.metric("Median views threshold", f"{median_views:,.0f}")
            c3.metric("Median purchase-rate threshold", f"{median_rate:.1%}")

            st.markdown("### How an opportunity is identified")
            st.markdown(
                "A product qualifies when it has **at least the minimum view floor**, "
                "**below-median views**, an **above-median view-to-purchase rate**, and "
                "**sufficient view data** (not flagged). Ranking uses the lower bound of "
                "each product's confidence interval, so a product with a thin sample and "
                "a lucky high rate won't outrank a product with a smaller but more certain edge."
            )

            cat_options = sorted(opportunities["item_category"].dropna().unique().tolist())
            selected_cats = st.multiselect(
                "Filter opportunities by category", cat_options, default=[],
                key="opportunity_categories"
            )
            max_results = st.slider(
                "Number of opportunities to display", min_value=5,
                max_value=min(50, len(opportunities)), value=min(15, len(opportunities)),
                key="opportunity_count"
            )

            view = opportunities.copy()
            if selected_cats:
                view = view[view["item_category"].isin(selected_cats)]
            view = view.head(max_results)

            if view.empty:
                st.warning("No opportunities match this category filter.")
            else:
                fig = px.scatter(
                    view,
                    x="sessions_viewed",
                    y="view_to_buy_rate",
                    size="revenue",
                    color="item_category",
                    hover_name="item_name",
                    hover_data={
                        "sessions_viewed": ":,",
                        "sessions_purchased": ":,",
                        "view_to_buy_rate": ":.1%",
                        "view_to_buy_ci_low": ":.1%",
                        "revenue": ":$,.0f",
                    },
                    labels={
                        "sessions_viewed": "Sessions viewed",
                        "view_to_buy_rate": "View-to-purchase rate",
                        "item_category": "Category",
                    },
                    size_max=42,
                )
                fig.update_layout(height=480)
                st.plotly_chart(fig, use_container_width=True)

                st.markdown("### Recommended opportunity shortlist")
                for _, row in view.iterrows():
                    with st.container(border=True):
                        c1, c2 = st.columns([3, 1])
                        c1.markdown(f"**{row['item_name']}**  ·  {row['item_category']}")
                        c1.caption(
                            f"{row['sessions_viewed']:,} views · "
                            f"{row['view_to_buy_rate']:.1%} observed rate "
                            f"(at least {row['view_to_buy_ci_low']:.1%} with 95% confidence) · "
                            f"${row['revenue']:,.0f} revenue"
                        )
                        if pd.notna(row["replaces"]):
                            c1.caption(f"🔁 Suggested swap: replace **{row['replaces']}** (same category, weaker conversion)")
                        else:
                            c1.caption("🔁 No same-category replacement candidate found")
                        key = f"add_opp_{row['item_name']}"
                        if row["item_name"] in st.session_state.shortlist:
                            c2.button("✓ Added", key=key, disabled=True)
                        else:
                            if c2.button("+ Add to shortlist", key=key):
                                add_to_shortlist(row.to_dict())
                                st.rerun()

                csv_data = view[[
                    "item_name", "item_category", "sessions_viewed", "sessions_purchased",
                    "view_to_buy_rate", "view_to_buy_ci_low", "revenue", "replaces",
                ]].to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Download opportunity shortlist (CSV)",
                    data=csv_data,
                    file_name="holiday_shelf_opportunities.csv",
                    mime="text/csv",
                )

            st.caption(
                "Caution: the data covers a historical holiday season. These are candidates for "
                "merchandising tests, not guarantees of future performance."
            )

# ---------------------------------------------------------------------------
# PROMO CHECK (placeholder — Person B's B4, not tonight's scope)
# ---------------------------------------------------------------------------
elif page == "Promo Check":
    st.title("Promo Check")
    st.info("Becoming Banner Performance (B4) — not tonight's scope. Raw data below.")
    df = load_promo_check()
    st.dataframe(df.head(20), use_container_width=True)

# ---------------------------------------------------------------------------
# SEASON PLAYBOOK (placeholder — Person A's A2, not tonight's scope)
# ---------------------------------------------------------------------------
elif page == "Season Playbook":
    st.title("Season Playbook")
    st.info("Person A's build (A2) — not tonight's scope. Raw data below.")
    df = load_weekly()
    st.dataframe(df.head(20), use_container_width=True)

# ---------------------------------------------------------------------------
# SHORTLIST BUILDER (placeholder — Person A's A1, not tonight's scope)
# ---------------------------------------------------------------------------
elif page == "Shortlist Builder":
    st.title("Shortlist Builder")
    st.info("Person A's main deliverable (A1) — not tonight's scope.")
    if st.session_state.shortlist:
        st.markdown(f"**{len(st.session_state.shortlist)} products added so far from Scorecard / Opportunity Finder:**")
        st.dataframe(
            pd.DataFrame(st.session_state.shortlist.values())[
                ["item_name", "item_category", "sessions_viewed", "view_to_buy_rate", "revenue", "label"]
            ],
            use_container_width=True,
        )
        st.caption("This list carries over once Person A builds the real Shortlist Builder (phase assignment, slot, replaces, test plan, export).")
    else:
        st.caption("No products added yet — use the '+ Add' buttons on Scorecard or Opportunity Finder.")