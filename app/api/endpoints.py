from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.database_models import RefundModel, OrderModel
from agent.runner import run_agent_turn

router = APIRouter(prefix="/api/v1", tags=["Customer Support Agent"])


# --- Pydantic Schemas for Requests ---

class AgentChatRequest(BaseModel):
    user_message: str = Field(..., description="The message from the customer or support representative.")
    customer_id: str = Field(..., description="Verified customer ID associated with the session.")
    chat_history: Optional[List[dict]] = Field(default=[], description="Previous conversation turns.")


class SupervisorDecisionRequest(BaseModel):
    decision: str = Field(..., description="Decision status: 'APPROVED' or 'REJECTED'.")
    supervisor_id: str = Field(..., description="Unique ID of the approving supervisor.")
    notes: Optional[str] = Field(None, description="Optional supervisor notes or justification.")


# --- Endpoints ---

@router.post("/support/chat")
def support_agent_chat(payload: AgentChatRequest):
    """
    Main endpoint for driving agent interactions and tool invocations.
    """
    try:
        # Prepend customer context to guide the agent session securely
        contextualized_message = f"[Context: Customer ID '{payload.customer_id}'] {payload.user_message}"
        
        agent_response = run_agent_turn(
            user_message=contextualized_message,
            chat_history=payload.chat_history
        )
        return {
            "success": True,
            "response": agent_response
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent execution failed: {str(e)}"
        )


@router.get("/refunds/{refund_id}")
def get_refund_status(refund_id: str, db: Session = Depends(get_db)):
    """
    Polls the status of a specific refund request (supports HITL tracking).
    """
    refund = db.query(RefundModel).filter_by(refund_id=refund_id).first()
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund request not found.")
    
    return {
        "success": True,
        "refund_id": refund.refund_id,
        "order_id": refund.order_id,
        "customer_id": refund.customer_id,
        "amount": refund.amount,
        "currency": refund.currency,
        "status": refund.status,
        "supervisor_id": refund.supervisor_id,
        "created_at": refund.created_at.isoformat(),
        "updated_at": refund.updated_at.isoformat()
    }


@router.post("/refunds/{refund_id}/decision")
def process_supervisor_decision(
    refund_id: str, 
    payload: SupervisorDecisionRequest, 
    db: Session = Depends(get_db)
):
    """
    Supervisor endpoint for approving or rejecting pending high-value refunds (HITL workflow).
    """
    refund = db.query(RefundModel).filter_by(refund_id=refund_id).first()
    if not refund:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Refund request not found.")
    
    if refund.status != "PENDING_APPROVAL":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Refund is not pending approval. Current status: {refund.status}"
        )
    
    decision = payload.decision.upper()
    if decision not in ["APPROVED", "REJECTED"]:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid decision. Must be 'APPROVED' or 'REJECTED'.")

    try:
        if decision == "APPROVED":
            refund.status = "PROCESSING" # Ready for gateway payment processing
            refund.supervisor_id = payload.supervisor_id
        else:
            refund.status = "REJECTED"
            refund.supervisor_id = payload.supervisor_id
        
        db.commit()
        db.refresh(refund)

        return {
            "success": True,
            "refund_id": refund.refund_id,
            "status": refund.status,
            "message": f"Refund successfully {decision.lower()} by supervisor."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
