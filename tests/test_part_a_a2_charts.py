import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class TestA2Charts(unittest.TestCase):

    def open_playbook(self):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=60,
        ).run()

        app.sidebar.radio[0].set_value(
            "Season Playbook"
        ).run()

        selector = next(
            s for s in app.selectbox
            if s.label == "Choose a product to analyze"
        )

        selector.set_value(
            "Google Zip Hoodie F/C"
        ).run()

        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

        return app

    def test_01_chart_sections_render(self):
        app = self.open_playbook()

        content = "\n".join(
            str(element.value)
            for element in app.markdown
        )

        for heading in [
            "Product weekly sales trend",
            "Historical USPS shipping deadlines",
            "Holiday search timing comparison",
            "Historical product demand vs search interest",
        ]:
            with self.subTest(heading=heading):
                self.assertIn(heading, content)

    def test_02_shipping_deadline_selection(self):
        app = self.open_playbook()

        selector = next(
            w for w in app.multiselect
            if w.label == "Show USPS 2020 mail-by dates on chart"
        )

        selector.set_value([
            "Priority Mail Express — Dec 23"
        ]).run()

        self.assertFalse(app.exception)

        updated = next(
            w for w in app.multiselect
            if w.label == "Show USPS 2020 mail-by dates on chart"
        )

        self.assertEqual(
            updated.value,
            ["Priority Mail Express — Dec 23"],
        )

    def test_03_holiday_year_coverage(self):
        trends = pd.read_csv(
            ROOT / "data" / "google_trends_hoodie.csv",
            skiprows=2,
        )

        months = set(trends["Month"].astype(str))

        for year in [2020, 2025]:
            for month in [10, 11, 12]:
                self.assertIn(
                    f"{year}-{month:02d}",
                    months,
                )

        self.assertIn("2026-10", months)
        self.assertIn("2026-11", months)
        self.assertNotIn("2026-12", months)

    def test_04_historical_data_overlap(self):
        weekly = pd.read_csv(
            ROOT / "data" / "weekly.csv"
        )

        product = weekly[
            weekly["item_name"] == "Google Zip Hoodie F/C"
        ].copy()

        product["month"] = pd.to_datetime(
            product["week_start"]
        ).dt.to_period("M").astype(str)

        trends = pd.read_csv(
            ROOT / "data" / "google_trends_hoodie.csv",
            skiprows=2,
        )

        overlap = set(product["month"]) & set(
            trends["Month"].astype(str)
        )

        for month in [
            "2020-10",
            "2020-11",
            "2020-12",
            "2021-01",
        ]:
            self.assertIn(month, overlap)


if __name__ == "__main__":
    unittest.main()
