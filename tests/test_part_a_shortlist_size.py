import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class TestShortlistSize(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.products = pd.read_csv(
            ROOT / "data" / "product_summary.csv"
        )

    def open_with_products(self, count):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=60,
        ).run()

        rows = self.products.head(count)
        app.session_state["shortlist"] = {
            row["item_name"]: row.to_dict()
            for _, row in rows.iterrows()
        }

        app.sidebar.radio[0].set_value(
            "Shortlist Builder"
        ).run()

        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

        return app

    def test_below_recommended_range(self):
        app = self.open_with_products(5)
        messages = " ".join(
            str(x.value) for x in app.info
        )
        self.assertIn("Add at least 5 more", messages)

    def test_within_recommended_range(self):
        app = self.open_with_products(12)
        messages = " ".join(
            str(x.value) for x in app.success
        )
        self.assertIn(
            "12-product shortlist is within",
            messages,
        )

    def test_above_recommended_range(self):
        app = self.open_with_products(16)
        messages = " ".join(
            str(x.value) for x in app.warning
        )
        self.assertIn("removing 1", messages)


if __name__ == "__main__":
    unittest.main()
