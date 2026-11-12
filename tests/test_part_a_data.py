import unittest
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class TestPartAData(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.products = pd.read_csv(DATA / "product_summary.csv")
        cls.weekly = pd.read_csv(DATA / "weekly.csv")
        cls.orders = pd.read_csv(DATA / "orders_v2.csv")

    def test_01_required_files_exist(self):
        for name in [
            "product_summary.csv",
            "weekly.csv",
            "orders_v2.csv",
        ]:
            with self.subTest(file=name):
                self.assertTrue((DATA / name).is_file())

    def test_02_product_columns(self):
        required = {
            "item_name",
            "item_category",
            "sessions_viewed",
            "sessions_purchased",
            "view_to_buy_rate",
            "label",
        }
        self.assertTrue(required.issubset(self.products.columns))

    def test_03_weekly_columns(self):
        required = {
            "item_name",
            "week_start",
            "phase",
            "sessions_viewed",
            "sessions_purchased",
            "revenue",
        }
        self.assertTrue(required.issubset(self.weekly.columns))

    def test_04_product_names(self):
        self.assertFalse(self.products["item_name"].isna().any())
        self.assertFalse(self.weekly["item_name"].isna().any())
        self.assertFalse(self.orders["item_name"].isna().any())

    def test_05_unique_summary_products(self):
        duplicates = self.products["item_name"].duplicated()
        self.assertFalse(
            duplicates.any(),
            f"Duplicate products: {duplicates.sum()}",
        )

    def test_06_holiday_phases(self):
        expected = {
            "Early Nov",
            "Black Friday / Cyber Monday",
            "Mid-Dec",
            "Post-Christmas",
        }
        actual = set(self.weekly["phase"].dropna().unique())
        self.assertEqual(actual, expected)

    def test_07_valid_weekly_dates(self):
        dates = pd.to_datetime(
            self.weekly["week_start"],
            errors="coerce",
        )
        self.assertFalse(dates.isna().any())

    def test_08_nonnegative_session_counts(self):
        for df in [self.products, self.weekly]:
            for column in [
                "sessions_viewed",
                "sessions_purchased",
            ]:
                with self.subTest(column=column):
                    values = pd.to_numeric(
                        df[column], errors="coerce"
                    )
                    self.assertFalse(values.isna().any())
                    self.assertTrue((values >= 0).all())

    def test_09_valid_order_prices(self):
        prices = pd.to_numeric(
            self.orders["price"], errors="coerce"
        )
        self.assertFalse(prices.isna().any())
        self.assertTrue((prices >= 0).all())

    def test_10_product_price_matches(self):
        known = set(self.products["item_name"])
        priced = set(self.orders["item_name"])
        self.assertGreater(len(known & priced), 0)


if __name__ == "__main__":
    unittest.main()
