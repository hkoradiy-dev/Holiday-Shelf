import unittest
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class TestShortlistBuilder(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.products = pd.read_csv(
            ROOT / "data" / "product_summary.csv"
        )
        cls.product_name = "Google Keychain"
        matches = cls.products[
            cls.products["item_name"] == cls.product_name
        ]
        assert len(matches) == 1
        cls.product = matches.iloc[0].to_dict()

    def new_app(self):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=30,
        ).run()
        self.check_app(app)
        return app

    def check_app(self, app):
        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

    def go_to(self, app, page):
        app.sidebar.radio[0].set_value(page).run()
        self.check_app(app)
        return app

    def app_with_product(self):
        app = self.new_app()
        app.session_state["shortlist"] = {
            self.product_name: self.product.copy()
        }
        return self.go_to(app, "Shortlist Builder")

    def widget(self, widgets, label):
        return next(w for w in widgets if w.label == label)

    def test_01_empty_shortlist(self):
        app = self.go_to(self.new_app(), "Shortlist Builder")
        messages = " ".join(str(x.value) for x in app.info)
        self.assertIn("shortlist is empty", messages.lower())

    def test_02_populated_shortlist(self):
        app = self.app_with_product()
        self.assertEqual(len(app.session_state["shortlist"]), 1)

        metrics = {m.label: str(m.value) for m in app.metric}
        self.assertEqual(metrics["Products selected"], "1")
        self.assertEqual(metrics["Products with price data"], "1")

    def test_03_change_holiday_phase(self):
        app = self.app_with_product()
        self.widget(
            app.selectbox, "Holiday phase"
        ).set_value("Mid-Dec").run()

        self.check_app(app)
        self.assertEqual(
            app.session_state["shortlist"][
                self.product_name
            ]["holiday_phase"],
            "Mid-Dec",
        )

    def test_04_change_placement(self):
        app = self.app_with_product()
        self.widget(
            app.selectbox, "Placement slot"
        ).set_value("Category page").run()

        self.check_app(app)
        self.assertEqual(
            app.session_state["shortlist"][
                self.product_name
            ]["placement_slot"],
            "Category page",
        )

    def test_05_cart_addon_placement(self):
        app = self.app_with_product()
        self.widget(
            app.selectbox, "Placement slot"
        ).set_value("Cart add-on").run()

        self.check_app(app)

        item = app.session_state["shortlist"][
            self.product_name
        ]
        self.assertEqual(item["placement_slot"], "Cart add-on")
        self.assertIsNone(item["replacement_product"])

    def test_06_replacement_dropdown(self):
        app = self.app_with_product()
        replacement = self.widget(
            app.selectbox, "Product to replace"
        )

        self.assertIn(
            "No replacement",
            replacement.options,
        )
        self.assertFalse(
            any(
                str(option).lower() == "nan"
                for option in replacement.options
            )
        )

    def test_07_add_from_scorecard(self):
        app = self.new_app()

        add_buttons = [
            b for b in app.button
            if b.label == "+ Add" and not b.disabled
        ]
        self.assertTrue(add_buttons)

        add_buttons[0].click().run()
        self.check_app(app)

        self.assertEqual(
            len(app.session_state["shortlist"]), 1
        )

        self.go_to(app, "Shortlist Builder")
        self.assertEqual(
            len(app.session_state["shortlist"]), 1
        )

    def test_08_remove_from_sidebar(self):
        app = self.app_with_product()

        remove_buttons = [
            b for b in app.sidebar.button
            if b.label == "✕"
        ]
        self.assertEqual(len(remove_buttons), 1)

        remove_buttons[0].click().run()
        self.check_app(app)

        self.assertEqual(
            len(app.session_state["shortlist"]), 0
        )


if __name__ == "__main__":
    unittest.main()
