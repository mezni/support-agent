import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, EmailStr

from app.core.database import SessionLocal
from app.models.database_models import CustomerModel, OrderModel, InvoiceModel, RefundModel
from app.services.policy_engine import policy_engine


# --- Pydantic Argument Validation Schemas ---

class CustomerAccountInput(BaseModel):
    customer_id: str = Field(..., description="The unique identifier of the customer.")

class OrderHistoryInput(BaseModel):
    customer_id: str = Field(..., description="The unique identifier of the customer.")

class DeliveryStatusInput(BaseModel):
    order_id: str = Field(..., description="The unique identifier of the order.")

class BillingHistoryInput(BaseModel):
    customer_id: str = Field(..., description="The unique identifier of the customer.")

class RefundEligibilityInput(BaseModel):
    order_id: str = Field(..., description="The unique identifier of the order to evaluate.")
    amount: float = Field(..., gt=0, description="The requested refund amount.")

class ReturnRequestInput(BaseModel):
    order_id: str = Field(..., description="The unique order ID for the return.")
    customer_id: str = Field(..., description="The customer ID initiating the return.")
    reason: str = Field(..., description="Reason for the return request.")
    idempotency_key: str = Field(..., description="Unique idempotency key to prevent duplicate requests.")

class IssueRefundInput(BaseModel):
    order_id: str = Field(..., description="The unique order ID for the refund.")
    customer_id: str = Field(..., description="The customer ID requesting the refund.")
    amount: float = Field(..., gt=0, description="The refund amount.")
    reason: str = Field(..., description="Reason for the refund.")
    idempotency_key: str = Field(..., description="Unique idempotency key for financial write safety.")


# --- Tool Implementation Functions ---

def get_customer_account(customer_id: str) -> Dict[str, Any]:
    """Retrieves customer account details securely."""
    db = SessionLocal()
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
                "created_at": customer.created_at.isoformat()
            }
        }
    finally:
        db.close()


def get_order_history(customer_id: str) -> Dict[str, Any]:
    """Retrieves all order records associated with a customer."""
    db = SessionLocal()
    try:
        orders = db.query(OrderModel).filter_by(customer_id=customer_id).all()
        order_list = [
            {
                "order_id": o.order_id,
                "status": o.status,
                "total_amount": o.total_amount,
                "currency": o.currency,
                "created_at": o.created_at.isoformat()
            }
            for o in orders
        ]
        return {"success": True, "data": order_list}
    finally:
        db.close()


def get_delivery_status(order_id: str) -> Dict[str, Any]:
    """Checks the delivery and shipping status of an order."""
    db = SessionLocal()
    try:
        order = db.query(OrderModel).filter_by(order_id=order_id).first()
        if not order:
            return {"success": False, "error": "Order not found."}
        
        return {
            "success": True,
            "data": {
                "order_id": order.order_id,
                "status": order.status,
                "order_date": order.created_at.isoformat()
            }
        }
    finally:
        db.close()


def get_billing_history(customer_id: str) -> Dict[str, Any]:
    """Retrieves invoice and billing history for a customer's orders."""
    db = SessionLocal()
    try:
        # Join orders and invoices for the given customer
        invoices = (
            db.query(InvoiceModel)
            .join(OrderModel, InvoiceModel.order_id == OrderModel.order_id)
            .filter(OrderModel.customer_id == customer_id)
            .all()
        )
        
        invoice_list = [
            {
                "invoice_id": inv.invoice_id,
                "order_id": inv.order_id,
                "amount": inv.amount,
                "status": inv.status,
                "issued_at": inv.issued_at.isoformat()
            }
            for inv in invoices
        ]
        return {"success": True, "data": invoice_list}
    finally:
        db.close()


def check_refund_eligibility(order_id: str, amount: float) -> Dict[str, Any]:
    """Evaluates refund eligibility using deterministic policy rules."""
    db = SessionLocal()
    try:
        order = db.query(OrderModel).filter_by(order_id=order_id).first()
        if not order:
            return {"success": False, "error": "Order not found."}
        
        # Pass order details to policy engine
        evaluation = policy_engine.evaluate_refund_eligibility(
            order_date=order.created_at,
            order_status=order.status,
            amount=amount
        )
        return {"success": True, "evaluation": evaluation}
    finally:
        db.close()


def create_return_request(order_id: str, customer_id: str, reason: str, idempotency_key: str) -> Dict[str, Any]:
    """Creates a return request with idempotency protection."""
    db = SessionLocal()
    try:
        # Check idempotency key
        existing = db.query(RefundModel).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return {
                "success": True,
                "message": "Duplicate request detected via idempotency key. Returning existing record.",
                "data": {"refund_id": existing.refund_id, "status": existing.status}
            }
        
        order = db.query(OrderModel).filter_by(order_id=order_id, customer_id=customer_id).first()
        if not order:
            return {"success": False, "error": "Order not found or customer mismatch."}

        # Create return/refund placeholder record in PENDING state
        refund_id = f"ref_{uuid.uuid4().hex[:12]}"
        new_refund = RefundModel(
            refund_id=refund_id,
            order_id=order_id,
            customer_id=customer_id,
            amount=order.total_amount,
            currency=order.currency,
            status="PENDING_APPROVAL",
            idempotency_key=idempotency_key,
            reason=reason
        )
        db.add(new_refund)
        db.commit()

        return {
            "success": True,
            "data": {
                "refund_id": refund_id,
                "status": "PENDING_APPROVAL",
                "message": "Return request created and queued."
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


def issue_refund(order_id: str, customer_id: str, amount: float, reason: str, idempotency_key: str) -> Dict[str, Any]:
    """Processes or queues a refund based on deterministic threshold policies with idempotency guards."""
    db = SessionLocal()
    try:
        # 1. Idempotency Check
        existing = db.query(RefundModel).filter_by(idempotency_key=idempotency_key).first()
        if existing:
            return {
                "success": True,
                "message": "Idempotent retry detected. Returning existing transaction status.",
                "data": {"refund_id": existing.refund_id, "status": existing.status}
            }

        # 2. Fetch Order & Validate Eligibility via Policy Engine
        order = db.query(OrderModel).filter_by(order_id=order_id, customer_id=customer_id).first()
        if not order:
            return {"success": False, "error": "Order not found or customer mismatch."}

        evaluation = policy_engine.evaluate_refund_eligibility(
            order_date=order.created_at,
            order_status=order.status,
            amount=amount
        )

        if not evaluation["is_eligible"]:
            return {"success": False, "error": evaluation["reason"], "error_code": evaluation["error_code"]}

        # 3. Determine Initial Status (HITL vs Automated)
        initial_status = "PENDING_APPROVAL" if evaluation["requires_approval"] else "PROCESSING"

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
        db.add(new_refund)
        db.commit()

        return {
            "success": True,
            "data": {
                "refund_id": refund_id,
                "status": initial_status,
                "requires_approval": evaluation["requires_approval"],
                "message": evaluation["reason"]
            }
        }
    except Exception as e:
        db.rollback()
        return {"success": False, "error": str(e)}
    finally:
        db.close()


# --- Tool Registry Mapping ---
TOOL_REGISTRY = {
    "get_customer_account": (get_customer_account, CustomerAccountInput),
    "get_order_history": (get_order_history, OrderHistoryInput),
    "get_delivery_status": (get_delivery_status, DeliveryStatusInput),
    "get_billing_history": (get_billing_history, BillingHistoryInput),
    "check_refund_eligibility": (check_refund_eligibility, RefundEligibilityInput),
    "create_return_request": (create_return_request, ReturnRequestInput),
    "issue_refund": (issue_refund, IssueRefundInput),
}
