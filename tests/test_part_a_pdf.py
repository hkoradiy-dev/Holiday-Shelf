import ast
import re
import unittest
from pathlib import Path
from io import BytesIO
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import landscape, letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
)


ROOT = Path(__file__).resolve().parents[1]


def load_pdf_builder():
    """Load the PDF function without launching Streamlit."""
    tree = ast.parse((ROOT / "app.py").read_text())

    matches = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "build_shelf_brief_pdf"
    ]

    if len(matches) != 1:
        raise AssertionError("Expected exactly one PDF function.")

    namespace = globals().copy()
    module = ast.Module(body=matches, type_ignores=[])

    exec(
        compile(module, str(ROOT / "app.py"), "exec"),
        namespace,
    )

    return namespace["build_shelf_brief_pdf"]


class TestPDFExport(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.build_pdf = staticmethod(load_pdf_builder())

    def make_data(self, count):
        shortlist = pd.DataFrame([
            {
                "item_name": f"Test Product {i}",
                "item_category": "Lifestyle",
                "holiday_phase": "Mid-Dec",
                "placement_slot": "Homepage",
                "typical_price": 19.99,
                "replacement_product": None,
                "replaces": None,
                "view_to_buy_rate": 0.05,
                "test_visits_per_variant": 8158,
            }
            for i in range(count)
        ])

        category_mix = pd.DataFrame([
            {
                "Category": "Lifestyle",
                "Products": count,
                "Share (%)": 100.0,
            }
        ])

        price_mix = pd.DataFrame([
            {
                "Price band": "$10–$24.99",
                "Products": count,
                "Share (%)": 100.0,
            }
        ])

        return shortlist, category_mix, price_mix

    def generate(self, count):
        return self.build_pdf(*self.make_data(count), 0)

    def count_pages(self, data):
        return len(re.findall(rb"/Type\s*/Page\b", data))

    def test_01_valid_pdf_signature(self):
        result = self.generate(2)
        self.assertTrue(result.startswith(b"%PDF-"))
        self.assertIn(b"%%EOF", result)

    def test_02_single_product(self):
        self.assertEqual(self.count_pages(self.generate(1)), 1)

    def test_03_ten_products(self):
        self.assertEqual(self.count_pages(self.generate(10)), 1)

    def test_04_fifteen_products(self):
        self.assertEqual(self.count_pages(self.generate(15)), 1)

    def test_05_twenty_products(self):
        self.assertEqual(self.count_pages(self.generate(20)), 1)

    def test_06_missing_values(self):
        shortlist, categories, prices = self.make_data(2)

        shortlist.loc[0, "typical_price"] = None
        shortlist.loc[0, "view_to_buy_rate"] = None
        shortlist.loc[0, "test_visits_per_variant"] = None

        result = self.build_pdf(
            shortlist, categories, prices, 1
        )

        self.assertTrue(result.startswith(b"%PDF-"))
        self.assertEqual(self.count_pages(result), 1)

    def test_07_special_characters(self):
        shortlist, categories, prices = self.make_data(2)

        shortlist.loc[0, "item_name"] = "Bag & Bottle <Holiday>"
        shortlist.loc[0, "replacement_product"] = "Old & New"

        result = self.build_pdf(
            shortlist, categories, prices, 0
        )

        self.assertEqual(self.count_pages(result), 1)

    def test_08_cart_addon(self):
        shortlist, categories, prices = self.make_data(2)

        shortlist.loc[0, "placement_slot"] = "Cart add-on"
        shortlist.loc[0, "paired_with"] = "Google Hoodie"

        result = self.build_pdf(
            shortlist, categories, prices, 0
        )

        self.assertEqual(self.count_pages(result), 1)


if __name__ == "__main__":
    unittest.main()
