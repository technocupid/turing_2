# app/services/payment.py
"""
Minimal payment service abstraction.

This is a fake / mock implementation suitable for local development and tests.
Replace this with a real payment gateway integration (Stripe, Razorpay, PayPal)
when you go to production.
"""
from typing import Dict, Any
import uuid
import time


class PaymentError(Exception):
    pass


def process_payment(amount: float, payment_method: Dict[str, Any]) -> Dict[str, Any]:
    """
    Simulate processing a payment.

    Args:
        amount: amount in currency units (e.g. rupees / dollars)
        payment_method: dictionary describing payment method. For mock we accept:
            {"type": "card", "card_last4": "4242"} or {"type":"mock"}
    Returns:
        dict with keys: success(bool), transaction_id(str), amount(float), message(str)
    Raises:
        PaymentError on simulated failures.
    """
    # simple validations
    if amount is None or amount <= 0:
        raise PaymentError("invalid amount")

    pm_type = (payment_method or {}).get("type", "mock")

    # Simulate small delay (commented out to avoid blocking in sync contexts)
    # time.sleep(0.1)

    # Deterministic-ish transaction id
    txid = f"tx_{uuid.uuid4().hex[:16]}"

    if pm_type == "card":
        # Basic "decline" simulation: if card_last4 ends with '0' -> decline
        last4 = payment_method.get("card_last4", "")
        if str(last4).endswith("0"):
            return {"success": False, "transaction_id": txid, "amount": amount, "message": "card declined"}
        return {"success": True, "transaction_id": txid, "amount": amount, "message": "approved (mock)"}

    if pm_type == "offline":
        # offline payment - mark as pending
        return {"success": True, "transaction_id": txid, "amount": amount, "message": "marked pending (offline)"}

    # default mock succeeds
    return {"success": True, "transaction_id": txid, "amount": amount, "message": "mock success"}
