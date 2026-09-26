"""Find customers who placed an order."""


def customers_with_orders(customers: list[dict], orders: list[dict]) -> list[dict]:
    result = []
    for customer in customers:
        for order in orders:
            if order["customer_id"] == customer["id"]:
                result.append(customer)
                break
    return result


def unique_emails(customers: list[dict]) -> list[str]:
    emails = []
    for customer in customers:
        if customer["email"] not in emails:
            emails.append(customer["email"])
    return emails
