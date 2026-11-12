import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
TRENDS_FILE = ROOT / "data" / "google_trends_hoodie.csv"


class TestGoogleTrends(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.raw = pd.read_csv(TRENDS_FILE, skiprows=2)
        cls.months = pd.to_datetime(
            cls.raw["Month"].astype(str) + "-01",
            errors="coerce",
        )
        cls.scores = pd.to_numeric(
            cls.raw["hoodie: (United States)"],
            errors="coerce",
        )

    def test_01_file_exists(self):
        self.assertTrue(TRENDS_FILE.is_file())

    def test_02_observation_count(self):
        self.assertEqual(len(self.raw), 74)

    def test_03_valid_months(self):
        self.assertFalse(self.months.isna().any())
        self.assertFalse(self.months.duplicated().any())
        self.assertTrue(self.months.is_monotonic_increasing)

    def test_04_valid_interest_scores(self):
        self.assertFalse(self.scores.isna().any())
        self.assertTrue(self.scores.between(0, 100).all())

    def test_05_date_coverage(self):
        self.assertEqual(
            self.months.min(),
            pd.Timestamp("2020-10-01"),
        )
        self.assertEqual(
            self.months.max(),
            pd.Timestamp("2026-11-01"),
        )

    def test_06_overlapping_sales_months(self):
        weekly = pd.read_csv(ROOT / "data" / "weekly.csv")

        sales_months = set(
            pd.to_datetime(weekly["week_start"])
            .dt.to_period("M")
        )
        trends_months = set(self.months.dt.to_period("M"))

        self.assertTrue(
            sales_months.intersection(trends_months)
        )

    def test_07_charts_load_in_streamlit(self):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=30,
        ).run()

        app.sidebar.radio[0].set_value(
            "Season Playbook"
        ).run()

        selector = next(
            w for w in app.selectbox
            if w.label == "Choose a product to analyze"
        )
        selector.set_value("Google Zip Hoodie F/C").run()

        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

        headings = "\n".join(
            str(m.value) for m in app.markdown
        )

        self.assertIn(
            "Google Trends data comparison",
            headings,
        )
        self.assertIn(
            "Historical product demand vs search interest",
            headings,
        )


if __name__ == "__main__":
    unittest.main()
