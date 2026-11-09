def shipping_cost(total, express=False):
    """Shipping cost in USD for an order total."""
    if total < 0:
        raise ValueError("total must be >= 0")
    base = 5.0
    return base * 2 if express else base
