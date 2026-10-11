# Holiday Shelf

## Setup
```
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python pipeline.py              # reads data/raw_events.csv, writes product_summary.csv, weekly.csv, promo_check.csv
streamlit run app.py
```

## Project status
- ✅ Pipeline (`pipeline.py`) — working, tested against the real BigQuery export
- ✅ Shelf Scorecard page — working
- 🔜 Promo Check page — data is ready (`promo_check.csv`), chart not built yet
- 🔜 Season Playbook page — data is ready (`weekly.csv`), chart not built yet
- 🔜 Shortlist Builder page — not started
- 🔜 AI rationale layer — not started

## Known data limitations (read before presenting this)
1. **`view_item` undercounts exposure.** Confirmed via direct BigQuery diagnostic: many
   high-purchase products (gift cards, and ordinary merch) have zero `view_item` events but
   healthy `add_to_cart`/`purchase` counts. We define `sessions_exposed = sessions_viewed +
   sessions_added_to_cart` as the best available proxy. It is an upper-bound approximation,
   not an exact distinct-session count.
2. **~49% of products still have purchases exceeding tracked exposure** even after the fix
   above (flagged as `exposure_likely_undercounted` in `product_summary.csv`). This means some
   purchase paths (e.g. reorders) aren't captured by either `view_item` or `add_to_cart`.
3. **`item_category` was unreliable in the raw export** — the same `item_id` had different
   category breadcrumbs across rows. The pipeline collapses this to one canonical category per
   product (most frequent non-null value); treat category filters as approximate.
4. **Quadrant labels use a median split**, and this dataset is zero-inflated (most products in
   the eligible set had zero purchases in-window) — the split uses strict `>` against the
   median specifically to handle a median of 0 correctly. Read `pipeline.py`'s `label_row()`
   comments for the full reasoning.
5. **Single holiday season (Nov 2020 – Jan 2021).** Quadrant placement is a hypothesis to test
   this year, not a guarantee.
6. **Promo Check is correlational**, not causal — not yet built into the app, data is ready.

## Files
- `pipeline.py` — cleans raw export, computes funnel rates + Wilson CIs, labels quadrants
- `app.py` — Streamlit app (4-page sidebar nav)
- `data/raw_events.csv` — your BigQuery export (input, not regenerated)
- `data/product_summary.csv`, `data/weekly.csv`, `data/promo_check.csv` — pipeline output
