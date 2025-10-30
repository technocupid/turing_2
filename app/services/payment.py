import os
from typing import Dict, Any


class PaymentError(Exception):
    pass


def process_payment(amount: float, payment_info: Dict[str, Any]) -> Dict[str, Any]:
    """
    Minimal fake payment processor:
    - If payment_info.get("card_last4") == "4242" or payment_info.get("type") == "test" -> success
    - Otherwise returns a failure result.
    Returns: {"success": bool, "transaction_id": str|None, "message": str}
    """
    # simple deterministic test behavior
    if payment_info.get("type") == "test" or str(payment_info.get("card_last4") or "") == "4242":
        tx = f"tx_{os.urandom(6).hex()}"
        return {"success": True, "transaction_id": tx, "message": "ok"}
    return {"success": False, "transaction_id": None, "message": "declined"}


