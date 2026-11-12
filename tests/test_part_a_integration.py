import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]
JOURNAL = "#IamRemarkable Journal"


class TestPartAIntegration(unittest.TestCase):

    def check_app(self, app):
        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

    def open_season(self, existing_product=False):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=30,
        ).run()

        self.check_app(app)

        if existing_product:
            products = pd.read_csv(
                ROOT / "data" / "product_summary.csv"
            )

            row = products[
                products["item_name"] == JOURNAL
            ].iloc[0].to_dict()

            row["holiday_phase"] = "Early Nov"

            app.session_state["shortlist"] = {
                JOURNAL: row
            }

        app.sidebar.radio[0].set_value(
            "Season Playbook"
        ).run()

        self.check_app(app)

        return app

    def choose_product(self, app, name):
        selector = next(
            s for s in app.selectbox
            if s.label == "Choose a product to analyze"
        )

        selector.set_value(name).run()
        self.check_app(app)

    def find_button(self, app, label):
        return next(
            b for b in app.button
            if b.label == label
        )

    def test_01_add_recommended_product(self):
        app = self.open_season()
        self.choose_product(app, JOURNAL)

        self.find_button(
            app,
            "Add to shortlist with recommended phase",
        ).click().run()

        self.check_app(app)

        shortlist = app.session_state["shortlist"]

        self.assertEqual(len(shortlist), 1)
        self.assertIn(JOURNAL, shortlist)

        self.assertEqual(
            shortlist[JOURNAL]["holiday_phase"],
            "Mid-Dec",
        )

    def test_02_update_without_duplicate(self):
        app = self.open_season(existing_product=True)
        self.choose_product(app, JOURNAL)

        self.find_button(
            app,
            "Apply recommended phase to shortlist",
        ).click().run()

        self.check_app(app)

        shortlist = app.session_state["shortlist"]

        self.assertEqual(len(shortlist), 1)
        self.assertEqual(
            shortlist[JOURNAL]["holiday_phase"],
            "Mid-Dec",
        )

        app.sidebar.radio[0].set_value(
            "Shortlist Builder"
        ).run()

        self.check_app(app)

        phase_selector = next(
            s for s in app.selectbox
            if s.label == "Holiday phase"
        )

        self.assertEqual(
            phase_selector.value,
            "Mid-Dec",
        )

    def test_03_insufficient_evidence(self):
        app = self.open_season()
        self.choose_product(app, "Google Keychain")

        buttons = [
            b.label for b in app.button
        ]

        self.assertNotIn(
            "Add to shortlist with recommended phase",
            buttons,
        )

        self.assertNotIn(
            "Apply recommended phase to shortlist",
            buttons,
        )

        self.assertEqual(
            len(app.session_state["shortlist"]),
            0,
        )


if __name__ == "__main__":
    unittest.main()
