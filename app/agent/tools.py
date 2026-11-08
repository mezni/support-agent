from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.database_models import CustomerModel, OrderModel
from app.services.policy_engine import policy_engine
from app.services.refund_service import refund_service


class CheckRefundEligibilityArgs(BaseModel):
    order_id: str = Field(..., description="The unique order ID.")
    amount: float = Field(..., gt=0, description="The refund amount.")


class GetCustomerAccountArgs(BaseModel):
    customer_id: str = Field(..., description="The verified customer ID.")


class GetOrderHistoryArgs(BaseModel):
    customer_id: str = Field(..., description="The customer ID.")


def _get_db() -> Session:
    return SessionLocal()


def get_customer_account(customer_id: str) -> Dict[str, Any]:
    db = _get_db()
    try:
        customer = db.query(CustomerModel).filter_by(customer_id=customer_id).first()
        if not customer:
            return {"success": False, "error": "Customer not found."}
        return {
            "success": True,
            "data": {
                "customer_id": customer.customer_id,
                "email": customer.email,
                "full_name": customer.full_name,
                "tier": customer.tier,
            },
        }
    finally:
        db.close()


def get_order_history(customer_id: str) -> Dict[str, Any]:
    db = _get_db()
    try:
        orders = (
            db.query(OrderModel)
            .filter_by(customer_id=customer_id)
            .all()
        )
        data = [
            {
                "order_id": o.order_id,
                "status": o.status,
                "total_amount": o.total_amount,
                "currency": o.currency,
                "created_at": o.created_at.isoformat() if o.created_at else None,
            }
            for o in orders
        ]
        return {"success": True, "data": data}
    finally:
        db.close()


def check_refund_eligibility(**kwargs: Any) -> Dict[str, Any]:
    args = CheckRefundEligibilityArgs(**kwargs)
    db = _get_db()
    try:
        order_obj = db.query(OrderModel).filter_by(order_id=args.order_id).first()
        if not order_obj:
            return {"success": False, "error": "Order not found."}

        evaluation = policy_engine.evaluate_refund_eligibility(
            order_date=order_obj.created_at,
            order_status=order_obj.status,
            amount=args.amount,
        )

        return {
            "success": True,
            "evaluation": {
                "is_eligible": evaluation["is_eligible"],
                "requires_approval": evaluation["requires_approval"],
                "reason": evaluation["reason"],
                "error_code": evaluation["error_code"],
            },
        }
    finally:
        db.close()


def create_return_request(
    order_id: str,
    customer_id: str,
    reason: str,
    idempotency_key: str,
    amount: Optional[float] = None,
) -> Dict[str, Any]:
    db = _get_db()
    try:
        # If amount not provided, lookup order and use its total_amount
        if amount is None:
            order = db.query(OrderModel).filter_by(order_id=order_id, customer_id=customer_id).first()
            if order:
                amount = order.total_amount
        
        result = refund_service.process_refund(
            db=db,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount if amount else 0.0,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return result
    finally:
        db.close()


def issue_refund(
    order_id: str,
    customer_id: str,
    amount: float,
    reason: str,
    idempotency_key: str,
) -> Dict[str, Any]:
    db = _get_db()
    try:
        result = refund_service.process_refund(
            db=db,
            order_id=order_id,
            customer_id=customer_id,
            amount=amount,
            reason=reason,
            idempotency_key=idempotency_key,
        )
        return result
    finally:
        db.close()


TOOL_REGISTRY: Dict[str, tuple] = {
    "get_customer_account": (get_customer_account, GetCustomerAccountArgs),
    "get_order_history": (get_order_history, GetOrderHistoryArgs),
    "check_refund_eligibility": (check_refund_eligibility, CheckRefundEligibilityArgs),
    "create_return_request": (create_return_request, None),
    "issue_refund": (issue_refund, None),
}