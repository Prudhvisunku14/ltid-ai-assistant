"""Scripted replies for the OFFLINE demo of the D5 loop. This is NOT an LLM: it only proves the plan/implement/test/repair/rollback
machinery works. Real unseen requests need a live LLM (OPENAI_API_KEY)."""
import json

REQUEST = "Free standard shipping for orders of 100 or more; express shipping is never free"
_BUGGY = '''def shipping_cost(total, express=False):
    """Shipping cost in USD for an order total."""
    if total < 0:
        raise ValueError("total must be >= 0")
    if total >= 100:
        return 0.0
    base = 5.0
    return base * 2 if express else base
'''
_FIXED = '''def shipping_cost(total, express=False):
    """Shipping cost in USD for an order total. Standard is free from 100; express is never free."""
    if total < 0:
        raise ValueError("total must be >= 0")
    if express:
        return 10.0
    return 0.0 if total >= 100 else 5.0
'''
_TESTS = '''import unittest
from shipping import shipping_cost


class TestShipping(unittest.TestCase):
    def test_base(self): self.assertEqual(shipping_cost(20), 5.0)
    def test_express(self): self.assertEqual(shipping_cost(20, express=True), 10.0)
    def test_negative(self):
        with self.assertRaises(ValueError): shipping_cost(-1)
    def test_free_at_100(self): self.assertEqual(shipping_cost(100), 0.0)
    def test_just_under_100(self): self.assertEqual(shipping_cost(99.99), 5.0)
    def test_express_never_free(self): self.assertEqual(shipping_cost(150, express=True), 10.0)


if __name__ == "__main__":
    unittest.main()
'''


def scripted_replies():
    plan = {"approach": "Add a >=100 threshold for standard shipping only; keep negative validation first.",
            "files_to_change": ["shipping.py", "test_shipping.py"],
            "tests_to_add": ["free at 100", "5.0 at 99.99", "express never free"], "risks": ["express orders over 100"]}
    return [json.dumps(plan),
            json.dumps({"files": [{"path": "shipping.py", "content": _BUGGY}, {"path": "test_shipping.py", "content": _TESTS}]}),
            json.dumps({"files": [{"path": "shipping.py", "content": _FIXED}]})]
