import unittest
from datetime import date
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class TestSeasonPlaybook(unittest.TestCase):

    def open_season(self):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=30,
        ).run()

        self.assertFalse(app.exception)

        app.sidebar.radio[0].set_value(
            "Season Playbook"
        ).run()

        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

        return app

    def choose_product(self, app, product):
        widget = next(
            s for s in app.selectbox
            if s.label == "Choose a product to analyze"
        )
        widget.set_value(product).run()
        self.assertFalse(app.exception)
        return app

    def choose_phase(self, app, phase):
        widget = next(
            s for s in app.selectbox
            if s.label == "Phase to schedule"
        )
        widget.set_value(phase).run()
        self.assertFalse(app.exception)
        return app

    def page_text(self, elements):
        return "\n".join(str(e.value) for e in elements)

    def test_01_page_loads(self):
        app = self.open_season()

        self.assertEqual(
            app.title[0].value,
            "Season Playbook",
        )

    def test_02_phase_totals_match_data(self):
        app = self.open_season()

        shown = app.dataframe[0].value
        source = pd.read_csv(
            ROOT / "data" / "weekly.csv"
        )

        for phase in source["phase"].unique():
            row = shown[
                shown["Phase"] == phase
            ].iloc[0]

            original = source[
                source["phase"] == phase
            ]

            self.assertEqual(
                int(row["Views"]),
                int(original["sessions_viewed"].sum()),
            )
            self.assertEqual(
                int(row["Purchases"]),
                int(original["sessions_purchased"].sum()),
            )

    def test_03_product_recommendation(self):
        app = self.open_season()
        self.choose_product(
            app, "#IamRemarkable Journal"
        )

        messages = self.page_text(app.info)

        self.assertIn(
            "Suggested historical phase to test: Mid-Dec",
            messages,
        )

    def test_04_insufficient_evidence(self):
        app = self.open_season()
        self.choose_product(app, "Google Keychain")

        messages = self.page_text(app.warning)

        self.assertIn(
            "insufficient historical evidence",
            messages,
        )

    def test_05_black_friday_2026_dates(self):
        app = self.open_season()
        self.choose_product(
            app, "#IamRemarkable Journal"
        )
        self.choose_phase(
            app, "Black Friday / Cyber Monday"
        )

        content = self.page_text(app.markdown)

        self.assertIn("Nov 27, 2026", content)
        self.assertIn("Nov 30, 2026", content)

    def test_06_shipping_cutoff_inside_phase(self):
        app = self.open_season()
        self.choose_product(
            app, "#IamRemarkable Journal"
        )
        self.choose_phase(app, "Mid-Dec")

        app.date_input[0].set_value(
            date(2026, 12, 16)
        ).run()

        self.assertFalse(app.exception)

        warnings = self.page_text(app.warning)

        self.assertIn(
            "extends beyond",
            warnings,
        )

    def test_07_shipping_cutoff_before_phase(self):
        app = self.open_season()
        self.choose_product(
            app, "#IamRemarkable Journal"
        )
        self.choose_phase(app, "Mid-Dec")

        app.date_input[0].set_value(
            date(2026, 11, 16)
        ).run()

        self.assertFalse(app.exception)

        warnings = self.page_text(app.warning)

        self.assertIn(
            "begins after",
            warnings,
        )

    def test_08_shipping_cutoff_at_phase_end(self):
        app = self.open_season()
        self.choose_product(
            app, "#IamRemarkable Journal"
        )
        self.choose_phase(app, "Mid-Dec")

        app.date_input[0].set_value(
            date(2026, 12, 24)
        ).run()

        self.assertFalse(app.exception)

        messages = self.page_text(app.success)

        self.assertIn(
            "ends before or on",
            messages,
        )


if __name__ == "__main__":
    unittest.main()
