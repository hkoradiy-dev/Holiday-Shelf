"""

1. data/name_crosswalk.csv  (built FROM THE DATA by find_name_crosswalk.sql)
   Looks at sessions where a shopper added product A to the cart and then bought
   product B, where B has (almost) no cart events of its own. If one A accounts for
   most of B's purchase sessions, has the same price, and clearly beats the runner-up,
   then B is just another spelling of A. No guessing from the words in the names.

2. data/name_aliases.csv  (small, hand-checked)
   Manual overrides. Anything listed here wins over the crosswalk. Use it for pairs
   a person has checked by eye, or to fix a case the crosswalk could not decide.

Both files are optional. If neither exists, names are left as they are.
"""

from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
CROSSWALK_PATH = DATA_DIR / "name_crosswalk.csv"
ALIASES_PATH = DATA_DIR / "name_aliases.csv"

# A crosswalk row is accepted only when ALL of these hold.
MIN_SESSIONS_TOGETHER = 5   # enough sessions that it is not a coincidence
MIN_SHARE = 0.60            # cart product A is in >= 60% of B's purchase sessions
MIN_MARGIN = 2.0            # ...and at least 2x the runner-up candidate's share


def _crosswalk_map() -> dict:
    if not CROSSWALK_PATH.exists():
        return {}
    cw = pd.read_csv(CROSSWALK_PATH)
    if cw.empty:
        return {}
    cw["price_match"] = cw["price_match"].astype(str).str.lower().isin(["true", "1"])
    mapping = {}
    for purchase_name, g in cw.groupby("purchase_name"):
        g = g.sort_values("candidate_rank")
        top = g.iloc[0]
        runner_up_share = g.iloc[1]["share_of_purchase_sessions"] if len(g) > 1 else 0.0
        ok = (
            top["candidate_rank"] == 1
            and top["sessions_together"] >= MIN_SESSIONS_TOGETHER
            and top["share_of_purchase_sessions"] >= MIN_SHARE
            and top["share_of_purchase_sessions"] >= MIN_MARGIN * runner_up_share
            and bool(top["price_match"])
            and top["cart_name"] != purchase_name
        )
        if ok:
            mapping[purchase_name] = top["cart_name"]
    return mapping


def _manual_map() -> dict:
    if not ALIASES_PATH.exists():
        return {}
    a = pd.read_csv(ALIASES_PATH)
    return dict(zip(a["source_name"], a["canonical_name"]))


def load_name_map() -> dict:
    """{name as it appears in the data -> name to use}. Manual aliases override the crosswalk."""
    mapping = _crosswalk_map()
    mapping.update(_manual_map())
    return mapping


def describe_name_map() -> pd.DataFrame:
    """Every applied rename with where it came from, for review and the README."""
    auto, manual = _crosswalk_map(), _manual_map()
    rows = [{"source_name": k, "canonical_name": v, "origin": "crosswalk (data)"}
            for k, v in auto.items() if k not in manual]
    rows += [{"source_name": k, "canonical_name": v, "origin": "manual alias"}
             for k, v in manual.items()]
    return pd.DataFrame(rows, columns=["source_name", "canonical_name", "origin"])