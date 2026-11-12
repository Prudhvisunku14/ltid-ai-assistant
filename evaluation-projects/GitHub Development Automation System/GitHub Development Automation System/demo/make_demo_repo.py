"""Creates the FICTIONAL repository 'bookshop-api' used for the demo."""
import subprocess
import sys
from pathlib import Path

FILES = {
"README.md": "# bookshop-api\n\nFictional mini back-end library for an online bookshop (pricing + stock).\n\nRun tests: `python -m unittest discover -s tests -t .`\n",
".gitignore": "__pycache__/\n*.pyc\n",
"Makefile": "test:\n\tpython -m unittest discover -s tests -t .\n",
"bookshop/__init__.py": '"""bookshop-api package."""\n',
"bookshop/pricing.py": '''"""Pricing helpers: price formatting and order totals."""


def format_price(cents: int) -> str:
    """Format an integer number of cents as a dollar string, e.g. 1999 -> '$19.99'."""
    return f"${cents // 100}.{cents % 100:02d}"


def calculate_total(items: list[dict]) -> int:
    """Return the order total in cents. Each item: {'sku': str, 'price_cents': int, 'qty': int}."""
    return sum(i["price_cents"] * i["qty"] for i in items)
''',
"bookshop/inventory.py": '''"""Tiny in-memory stock tracker."""


class Stock:
    def __init__(self) -> None:
        self._qty: dict[str, int] = {}

    def add(self, sku: str, qty: int) -> None:
        self._qty[sku] = self._qty.get(sku, 0) + qty

    def available(self, sku: str) -> int:
        return self._qty.get(sku, 0)
''',
"tests/__init__.py": "",
"tests/test_pricing.py": '''import unittest

from bookshop.pricing import calculate_total, format_price


class PricingTests(unittest.TestCase):
    def test_format_price(self):
        self.assertEqual(format_price(1999), "$19.99")

    def test_total_simple(self):
        items = [{"sku": "A", "price_cents": 1000, "qty": 2}]
        self.assertEqual(calculate_total(items), 2000)


if __name__ == "__main__":
    unittest.main()
''',
}


def main(dest: str) -> Path:
    root = Path(dest).resolve()
    if root.exists():
        raise SystemExit(f"{root} already exists; delete it first")
    for rel, text in FILES.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    g = lambda *a: subprocess.run(["git", "-C", str(root), "-c", "user.name=Demo", "-c", "user.email=demo@example.com", *a], check=True, capture_output=True)
    g("init", "-b", "main")
    g("add", "-A")
    g("commit", "-m", "Initial commit of fictional bookshop-api")
    print(f"created fictional repo at {root}")
    return root


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "demo_repo")
