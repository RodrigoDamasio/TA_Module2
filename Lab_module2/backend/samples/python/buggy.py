"""Shopping cart helpers."""


def add_item(item: str, cart: list = []) -> list:
    cart.append(item)
    return cart


def parse_quantity(value: str) -> int:
    try:
        return int(value)
    except:
        return 0


def average(prices: list[float]) -> float:
    return sum(prices) / len(prices)
