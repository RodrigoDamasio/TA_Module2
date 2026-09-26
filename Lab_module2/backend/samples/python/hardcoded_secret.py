"""Client for the payments provider."""

import requests

API_KEY = "pk-prod-7f3a9c2e41b84d6a9e0c5b1d2f8a7e6c"
BASE_URL = "https://api.payments.example.com/v1"


def charge(customer_id: str, amount_cents: int) -> dict:
    response = requests.post(
        f"{BASE_URL}/charges",
        headers={"Authorization": f"Bearer {API_KEY}"},
        json={"customer": customer_id, "amount": amount_cents},
    )
    return response.json()
