"""
Mock checkout service.

Architecture note (Layer 6 - Action):
  This service simulates the handoff to a merchant checkout system (e.g. Instacart).
  In production, replace this with a real API call to the merchant's cart/checkout API.
  The agent never sees payment credentials — it only receives a checkout URL to
  redirect the user to for final payment confirmation in the merchant's UI.

  To integrate a real merchant:
    1. Replace _create_instacart_session() with your Instacart API client call.
    2. Map MissingIngredient items to Instacart product SKUs.
    3. Use OAuth or API key auth — store credentials in environment variables, not code.
    4. Handle merchant errors and map them to HTTPExceptions.
    5. Store the real merchant order ID alongside checkout_session_id.
"""

from app.models.checkout import CheckoutSession
from app.models.proposal import PurchaseProposal
from app.services.repositories import checkout_repo

# Mock merchant base URL — replace with real merchant endpoint in production
MOCK_MERCHANT_BASE_URLS = {
    "Instacart": "https://mock.instacart.local/checkout",
    "Walmart": "https://mock.walmart.local/checkout",
    "Kroger": "https://mock.kroger.local/checkout",
}


def create_checkout_session(proposal: PurchaseProposal) -> CheckoutSession:
    """
    Generate a mock checkout session after proposal approval.

    In production: call the merchant API here with the cart items,
    receive a real checkout URL, and return it.
    """
    base_url = MOCK_MERCHANT_BASE_URLS.get(
        proposal.merchant,
        f"https://mock.merchant.local/checkout",
    )

    session = CheckoutSession(
        proposal_id=proposal.id,
        merchant=proposal.merchant,
        checkout_url=f"{base_url}/{proposal.id}",
        estimated_total=proposal.estimated_total,
        items_summary=", ".join(
            f"{item.name} x{item.missing_quantity}{item.unit}" for item in proposal.missing_items
        ),
    )

    checkout_repo.save(session)
    return session
