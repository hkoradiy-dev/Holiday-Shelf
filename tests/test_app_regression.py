import unittest
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT = Path(__file__).resolve().parents[1]


class TestAppRegression(unittest.TestCase):

    def check_page(self, page):
        app = AppTest.from_file(
            str(ROOT / "app.py"),
            default_timeout=30,
        ).run()

        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

        app.sidebar.radio[0].set_value(page).run()

        self.assertFalse(
            app.exception,
            [str(e.message) for e in app.exception],
        )

        self.assertTrue(app.title)
        self.assertEqual(app.title[0].value, page)

    def test_01_shelf_scorecard(self):
        self.check_page("Shelf Scorecard")

    def test_02_opportunity_finder(self):
        self.check_page("Opportunity Finder")

    def test_03_bundles_cart_rescue(self):
        self.check_page("Bundles & Cart Rescue")

    def test_04_promo_check(self):
        self.check_page("Promo Check")

    def test_05_season_playbook(self):
        self.check_page("Season Playbook")

    def test_06_shortlist_builder(self):
        self.check_page("Shortlist Builder")


if __name__ == "__main__":
    unittest.main()
