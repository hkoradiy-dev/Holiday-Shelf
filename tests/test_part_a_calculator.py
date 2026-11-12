import ast
import math
import unittest
from pathlib import Path
from statistics import NormalDist

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def load_calculator():
    """Load the real calculator without running Streamlit."""
    source = (ROOT / "app.py").read_text()
    tree = ast.parse(source)

    functions = [
        node for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "required_visits_per_variant"
    ]

    if len(functions) != 1:
        raise AssertionError(
            "Expected exactly one A/B calculator function."
        )

    namespace = {
        "pd": pd,
        "math": math,
        "NormalDist": NormalDist,
    }

    module = ast.Module(body=functions, type_ignores=[])
    exec(compile(module, str(ROOT / "app.py"), "exec"), namespace)

    return namespace["required_visits_per_variant"]


class TestABCalculator(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.calculate = staticmethod(load_calculator())

    def test_01_one_percent_baseline(self):
        self.assertEqual(self.calculate(0.01), 42693)

    def test_02_five_percent_baseline(self):
        self.assertEqual(self.calculate(0.05), 8158)

    def test_03_ten_percent_baseline(self):
        self.assertEqual(self.calculate(0.10), 3841)

    def test_04_twenty_five_percent_baseline(self):
        self.assertEqual(self.calculate(0.25), 1251)

    def test_05_zero_baseline(self):
        self.assertIsNone(self.calculate(0))

    def test_06_full_conversion_baseline(self):
        self.assertIsNone(self.calculate(1))

    def test_07_negative_baseline(self):
        self.assertIsNone(self.calculate(-0.1))

    def test_08_above_one_baseline(self):
        self.assertIsNone(self.calculate(1.1))

    def test_09_missing_baseline(self):
        for value in [None, float("nan")]:
            with self.subTest(value=value):
                self.assertIsNone(self.calculate(value))

    def test_10_invalid_relative_lift(self):
        for lift in [0, -0.2, 1.5]:
            with self.subTest(lift=lift):
                self.assertIsNone(
                    self.calculate(0.05, relative_lift=lift)
                )

    def test_11_positive_integer_result(self):
        for baseline in [0.01, 0.05, 0.10, 0.25, 0.50]:
            with self.subTest(baseline=baseline):
                result = self.calculate(baseline)
                self.assertIsInstance(result, int)
                self.assertGreater(result, 0)

    def test_12_lower_conversion_needs_more_traffic(self):
        self.assertGreater(
            self.calculate(0.01),
            self.calculate(0.10),
        )


if __name__ == "__main__":
    unittest.main()
