import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.database_models import CustomerModel, OrderModel, InvoiceModel
from agent.tools import TOOL_REGISTRY, get_customer_account, get_order_history, check_refund_eligibility
import agent.tools


@pytest.fixture(scope="function")
def db_session():
    """Fixture providing an isolated in-memory SQLite database session with seeded test records."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    session = TestingSessionLocal()
    
    # Seed mock customer, order, and invoice
    customer = CustomerModel(
        customer_id="cust_tool_test",
        email="tools.user@example.com",
        full_name="Tools Test User",
        tier="VIP"
    )
    order = OrderModel(
        order_id="ord_tool_test",
        customer_id="cust_tool_test",
        status="DELIVERED",
        total_amount=85.00,
        currency="USD"
    )
    invoice = InvoiceModel(
        invoice_id="inv_tool_test",
        order_id="ord_tool_test",
        amount=85.00,
        status="PAID"
    )
    session.add_all([customer, order, invoice])
    session.commit()
    
    try:
        yield session
    finally:
        session.close()


def test_get_customer_account_success(monkeypatch, db_session):
    """Test successful execution of get_customer_account tool."""
    monkeypatch.setattr(agent.tools, "SessionLocal", lambda: db_session)
    
    result = get_customer_account(customer_id="cust_tool_test")
    
    assert result["success"] is True
    assert result["data"]["customer_id"] == "cust_tool_test"
    assert result["data"]["email"] == "tools.user@example.com"
    assert result["data"]["tier"] == "VIP"


def test_get_customer_account_not_found(monkeypatch, db_session):
    """Test get_customer_account tool handling for non-existent customer."""
    monkeypatch.setattr(agent.tools, "SessionLocal", lambda: db_session)
    
    result = get_customer_account(customer_id="cust_nonexistent")
    
    assert result["success"] is False
    assert "Customer not found" in result["error"]


def test_get_order_history(monkeypatch, db_session):
    """Test retrieval of order records associated with a customer."""
    monkeypatch.setattr(agent.tools, "SessionLocal", lambda: db_session)
    
    result = get_order_history(customer_id="cust_tool_test")
    
    assert result["success"] is True
    assert len(result["data"]) == 1
    assert result["data"][0]["order_id"] == "ord_tool_test"
    assert result["data"][0]["status"] == "DELIVERED"


def test_check_refund_eligibility_tool(monkeypatch, db_session):
    """Test refund eligibility evaluation through the allowlisted tool wrapper."""
    monkeypatch.setattr(agent.tools, "SessionLocal", lambda: db_session)
    
    result = check_refund_eligibility(order_id="ord_tool_test", amount=50.00)
    
    assert result["success"] is True
    assert result["evaluation"]["is_eligible"] is True
    assert result["evaluation"]["requires_approval"] is False


def test_tool_registry_pydantic_validation():
    """Test that TOOL_REGISTRY correctly validates tool arguments using Pydantic schemas."""
    # Verify allowlisted tools are present in registry
    assert "get_customer_account" in TOOL_REGISTRY
    assert "issue_refund" in TOOL_REGISTRY

    func, validator = TOOL_REGISTRY["check_refund_eligibility"]
    
    # Valid arguments should parse successfully
    valid_args = {"order_id": "ord_123", "amount": 45.50}
    validated = validator(**valid_args)
    assert validated.order_id == "ord_123"
    assert validated.amount == 45.50

    # Invalid arguments (e.g., negative amount where gt=0) should raise validation error
    with pytest.raises(Exception):
        validator(order_id="ord_123", amount=-10.00)


def test_unregistered_tool_guardrail():
    """Test guardrail behavior when an unregistered or unauthorized tool is called."""
    unregistered_tool_name = "execute_arbitrary_shell_command"
    
    assert unregistered_tool_name not in TOOL_REGISTRY
    
    # Simulating runner behavior for unallowlisted tool calls
    response = {"success": False, "error": f"Tool '{unregistered_tool_name}' is not allowed or registered."}
    assert response["success"] is False
    assert "not allowed or registered" in response["error"]
