import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

from app.models.database_models import RefundModel, OrderModel
from app.services.policy_engine import policy_engine

class RefundService:
    """
    Dedicated service layer managing refund lifecycles, idempotency guards,
    and state transitions for the support agent.
    """

    @staticmethod
    def process_refund(
        db: Session,
        order_id: str,
        customer_id: str,
        amount: float,
        reason: str,
        idempotency_key: str
    ) -> Dict[str, Any]:
        """
        Processes a refund request with built-in idempotency protection and policy validation.
        """
        # 1. Idempotency Guard: Check if a transaction with this key already exists
        existing_refund = db.query(RefundModel).filter_by(idempotency_key=idempotency_key).first()
        if existing_refund:
            return {
                "success": True,
                "is_duplicate": True,
                "message": "Idempotent retry detected. Returning existing transaction record.",
                "data": {
                    "refund_id": existing_refund.refund_id,
                    "order_id": existing_refund.order_id,
                    "status": existing_refund.status,
                    "amount": existing_refund.amount,
                    "currency": existing_refund.currency
                }
            }

        # 2. Verify Order Existence and Ownership
        order = db.query(OrderModel).filter_by(order_id=order_id, customer_id=customer_id).first()
        if not order:
            return {
                "success": False,
                "error": "Order not found or customer mismatch.",
                "error_code": "ORDER_NOT_FOUND"
            }

        # 3. Evaluate Policy Engine Rules
        evaluation = policy_engine.evaluate_refund_eligibility(
            order_date=order.created_at,
            order_status=order.status,
            amount=amount
        )

        if not evaluation["is_eligible"]:
            return {
                "success": False,
                "error": evaluation["reason"],
                "error_code": evaluation["error_code"]
            }

        # 4. Determine Initial State (HITL Approval vs Automated Processing)
        initial_status = "PENDING_APPROVAL" if evaluation["requires_approval"] else "PROCESSING"

        # 5. Create and Persist Refund Record
        refund_id = f"ref_{uuid.uuid4().hex[:12]}"
        new_refund = RefundModel(
            refund_id=refund_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            currency=order.currency,
            status=initial_status,
            idempotency_key=idempotency_key,
            reason=reason
        )

        try:
            db.add(new_refund)
            db.commit()
            db.refresh(new_refund)
        except Exception as e:
            db.rollback()
            return {
                "success": False,
                "error": f"Database persistence failed: {str(e)}",
                "error_code": "DB_COMMIT_ERROR"
            }

        return {
            "success": True,
            "is_duplicate": False,
            "data": {
                "refund_id": refund_id,
                "status": initial_status,
                "requires_approval": evaluation["requires_approval"],
                "message": evaluation["reason"]
            }
        }

    @staticmethod
    def update_refund_status(
        db: Session,
        refund_id: str,
        new_status: str,
        supervisor_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Transitions a refund record to a new state (e.g., APPROVED, REJECTED, COMPLETED).
        """
        valid_statuses = {"PENDING_APPROVAL", "APPROVED", "REJECTED", "PROCESSING", "COMPLETED", "FAILED"}
        if new_status not in valid_statuses:
            return {
                "success": False, 
                "error": f"Invalid state transition target: '{new_status}'."
            }

        refund = db.query(RefundModel).filter_by(refund_id=refund_id).first()
        if not refund:
            return {
                "success": False, 
                "error": "Refund request not found."
            }

        refund.status = new_status
        if supervisor_id:
            refund.supervisor_id = supervisor_id
        refund.updated_at = datetime.now(timezone.utc)

        try:
            db.commit()
            db.refresh(refund)
            return {
                "success": True,
                "data": {
                    "refund_id": refund.refund_id,
                    "status": refund.status,
                    "supervisor_id": refund.supervisor_id,
                    "updated_at": refund.updated_at.isoformat()
                }
            }
        except Exception as e:
            db.rollback()
            return {
                "success": False, 
                "error": f"Failed to update status: {str(e)}"
            }

# Singleton instance for dependency injection
refund_service = RefundService()
