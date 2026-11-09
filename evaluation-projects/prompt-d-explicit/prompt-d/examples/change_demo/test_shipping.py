import unittest
from shipping import shipping_cost


class TestShipping(unittest.TestCase):
    def test_base(self): self.assertEqual(shipping_cost(20), 5.0)
    def test_express(self): self.assertEqual(shipping_cost(20, express=True), 10.0)
    def test_negative(self):
        with self.assertRaises(ValueError): shipping_cost(-1)


if __name__ == "__main__":
    unittest.main()
