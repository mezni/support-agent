from datetime import datetime, timezone
from typing import Dict, Any, Optional

class PolicyEngine:
    """
    Deterministic business logic engine for evaluating refund eligibility,
    return windows, and automated supervisor approval thresholds.
    """
    
    def __init__(self, return_window_days: int = 30, approval_threshold: float = 100.00):
        self.return_window_days = return_window_days
        self.approval_threshold = approval_threshold

    def evaluate_refund_eligibility(
        self, 
        order_date: datetime, 
        order_status: str, 
        amount: float,
        current_time: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Evaluates whether an order is eligible for a refund based on strict deterministic rules:
        1. Order must be in a deliverable state (e.g., DELIVERED).
        2. Refund request must be within the configured return window (default: 30 days).
        3. Refund amount must be greater than zero.
        4. Determines if human-in-the-loop (HITL) supervisor approval is required based on financial thresholds.
        """
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        
        # Ensure timezone compatibility for datetime calculations
        if order_date.tzinfo is None and current_time.tzinfo is not None:
            order_date = order_date.replace(tzinfo=timezone.utc)
        elif order_date.tzinfo is not None and current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # Rule 1: Order Status Validation
        if order_status.upper() not in ["DELIVERED", "COMPLETED"]:
            return {
                "is_eligible": False,
                "requires_approval": False,
                "reason": f"Order status is '{order_status}'. Refunds are only permitted for delivered orders.",
                "error_code": "INVALID_ORDER_STATUS"
            }

        # Rule 2: Return Window Expiration Check
        age_in_days = (current_time - order_date).days
        if age_in_days > self.return_window_days:
            return {
                "is_eligible": False,
                "requires_approval": False,
                "reason": f"Order age ({age_in_days} days) exceeds the allowed return window of {self.return_window_days} days.",
                "error_code": "RETURN_WINDOW_EXPIRED"
            }

        # Rule 3: Positive Amount Validation
        if amount <= 0:
            return {
                "is_eligible": False,
                "requires_approval": False,
                "reason": "Refund amount must be greater than zero.",
                "error_code": "INVALID_AMOUNT"
            }

        # Rule 4: Financial Threshold & Approval Evaluation (HITL)
        requires_approval = amount > self.approval_threshold
        
        return {
            "is_eligible": True,
            "requires_approval": requires_approval,
            "reason": (
                f"Refund eligible. Amount (${amount:.2f}) "
                f"{'exceeds' if requires_approval else 'is within'} the automated threshold (${self.approval_threshold:.2f}). "
                f"{'Requires supervisor approval (PENDING_APPROVAL).' if requires_approval else 'Eligible for automated processing.'}"
            ),
            "error_code": None
        }

# Singleton instance for dependency injection across services and tools
policy_engine = PolicyEngine(return_window_days=30, approval_threshold=100.00)
