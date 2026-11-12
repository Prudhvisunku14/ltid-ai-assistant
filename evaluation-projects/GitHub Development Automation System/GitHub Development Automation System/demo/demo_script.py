"""Scripted 'GPT' replies so the demo runs offline and deterministically.
The FIRST edit deliberately contains an off-by-one bug (`>` instead of `>=`) so you can watch
devbot detect the failing test and repair it. With --llm openai, real GPT answers replace all of this."""

PRICING_BUGGY = '''"""Pricing helpers: price formatting and order totals."""

BULK_THRESHOLD = 10          # total books in an order that triggers the discount
BULK_DISCOUNT_PERCENT = 10


def format_price(cents: int) -> str:
    """Format an integer number of cents as a dollar string, e.g. 1999 -> '$19.99'."""
    return f"${cents // 100}.{cents % 100:02d}"


def calculate_total(items: list[dict]) -> int:
    """Return the order total in cents, with a 10% bulk discount for 10+ books.

    Each item: {'sku': str, 'price_cents': int, 'qty': int}.
    """
    total = sum(i["price_cents"] * i["qty"] for i in items)
    quantity = sum(i["qty"] for i in items)
    if quantity > BULK_THRESHOLD:  # BUG: should be >=
        total = total * (100 - BULK_DISCOUNT_PERCENT) // 100
    return total
'''
PRICING_FIXED = PRICING_BUGGY.replace("quantity > BULK_THRESHOLD:  # BUG: should be >=", "quantity >= BULK_THRESHOLD:")

TESTS = '''import unittest

from bookshop.pricing import calculate_total, format_price


class PricingTests(unittest.TestCase):
    def test_format_price(self):
        self.assertEqual(format_price(1999), "$19.99")

    def test_total_simple(self):
        items = [{"sku": "A", "price_cents": 1000, "qty": 2}]
        self.assertEqual(calculate_total(items), 2000)

    def test_bulk_discount_applies_at_threshold(self):
        items = [{"sku": "A", "price_cents": 1000, "qty": 10}]
        self.assertEqual(calculate_total(items), 9000)

    def test_bulk_discount_counts_all_items(self):
        items = [{"sku": "A", "price_cents": 1000, "qty": 6}, {"sku": "B", "price_cents": 500, "qty": 6}]
        self.assertEqual(calculate_total(items), 8100)

    def test_no_discount_below_threshold(self):
        items = [{"sku": "A", "price_cents": 1000, "qty": 9}]
        self.assertEqual(calculate_total(items), 9000 + 0)


if __name__ == "__main__":
    unittest.main()
'''
# note: 9 * 1000 = 9000 with no discount; 10 * 1000 * 0.9 = 9000 too -> distinct inputs below keep tests meaningful.
TESTS = TESTS.replace('qty": 9}]\n        self.assertEqual(calculate_total(items), 9000 + 0)',
                      'qty": 9}]\n        self.assertEqual(calculate_total(items), 9000)\n\n    def test_threshold_boundary_is_cheaper_per_book(self):\n        nine = calculate_total([{"sku": "A", "price_cents": 1000, "qty": 9}])\n        ten = calculate_total([{"sku": "A", "price_cents": 1000, "qty": 10}])\n        self.assertLessEqual(ten, nine)')

SCRIPT = {
    "explain": {
        "overview": "bookshop-api is a small pure-Python library with a pricing module (price formatting, order totals) "
                    "and an in-memory stock tracker, tested with the standard-library unittest runner.",
        "important_files": [], "dev_tools": [],
    },
    "plan": {
        "summary": "Add a 10% bulk discount to calculate_total() for orders of 10 or more books, with tests.",
        "steps": [
            "Add BULK_THRESHOLD and BULK_DISCOUNT_PERCENT constants to bookshop/pricing.py",
            "Apply the discount in calculate_total() when total quantity >= threshold",
            "Add unit tests for below/at/above the threshold and for mixed-SKU orders",
            "Run the unittest suite and fix any failures",
        ],
        "files_to_change": ["bookshop/pricing.py", "tests/test_pricing.py"],
        "tools_required": [
            {"tool": "git", "why": "create branch and commit", "free_open_source": True},
            {"tool": "python unittest", "why": "run existing test suite", "free_open_source": True},
            {"tool": "GitHub REST API", "why": "open a draft pull request", "free_open_source": True},
        ],
        "risks": ["Integer rounding: discount uses floor division on cents"],
    },
    "edit": {"files": [
        {"path": "bookshop/pricing.py", "content": PRICING_BUGGY, "reason": "implement bulk discount"},
        {"path": "tests/test_pricing.py", "content": TESTS, "reason": "cover the new behaviour"},
    ]},
    "repair": [{
        "diagnosis": "Off-by-one: the condition used `>` so an order of exactly 10 books got no discount. Use `>=`.",
        "files": [{"path": "bookshop/pricing.py", "content": PRICING_FIXED, "reason": "fix threshold comparison"}],
    }],
    "summary": {
        "title": "Add 10% bulk discount for orders of 10+ books",
        "commit_message": "feat(pricing): 10% bulk discount for orders of 10 or more books",
        "body_markdown": "## What\nOrders with 10 or more books in total now get 10% off in `calculate_total()`.\n\n"
                         "## Why\nRequested bulk-order pricing.\n\n## How\n- New constants `BULK_THRESHOLD` / `BULK_DISCOUNT_PERCENT`\n"
                         "- Discount applied on total quantity across all SKUs (floor division on cents)\n"
                         "- New tests for below / at / above the threshold and mixed SKUs\n\n"
                         "## Notes\nFirst attempt failed the 'at threshold' test (`>` vs `>=`); fixed by the auto-repair step.",
    },
}
