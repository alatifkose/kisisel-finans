"""core/money.py — scale'e göre format/parse, float'sız."""

import unittest

from app.core.money import (
    format_amount,
    format_amount_with_grouping,
    parse_amount,
)


class FormatAmountTests(unittest.TestCase):
    def test_try_scale_2(self):
        self.assertEqual(format_amount(12345, 2), "123,45")

    def test_xau_scale_3(self):
        # Altın: sabit /100 olsaydı yanlış olurdu
        self.assertEqual(format_amount(2500, 3), "2,500")

    def test_scale_0(self):
        self.assertEqual(format_amount(100, 0), "100")

    def test_negative(self):
        self.assertEqual(format_amount(-12345, 2), "-123,45")

    def test_zero_padding(self):
        self.assertEqual(format_amount(5, 2), "0,05")

    def test_grouping(self):
        self.assertEqual(format_amount_with_grouping(1234567, 2), "12.345,67")

    def test_grouping_negative(self):
        self.assertEqual(format_amount_with_grouping(-100000000, 2), "-1.000.000,00")


class ParseAmountTests(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(parse_amount("123,45", 2), 12345)

    def test_xau(self):
        self.assertEqual(parse_amount("2,500", 3), 2500)

    def test_thousands_separator(self):
        self.assertEqual(parse_amount("1.234,56", 2), 123456)

    def test_invalid_raises(self):
        with self.assertRaises(ValueError):
            parse_amount("abc", 2)

    def test_round_trip(self):
        for value, scale in [(12345, 2), (2500, 3), (1, 2), (999999, 0)]:
            self.assertEqual(
                parse_amount(format_amount(value, scale), scale),
                value,
                msg=f"round-trip bozuldu: {value} scale={scale}",
            )


if __name__ == "__main__":
    unittest.main()
