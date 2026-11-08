import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.database_models import CustomerModel, OrderModel, RefundModel
from app.services.policy_engine import PolicyEngine
from agent.tools import create_return_request, issue_refund

# Setup an in-memory SQLite test database fixture
@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_policy_engine_automated_refund():
    """Test that an order delivered within 30 days and under the threshold is eligible for automation."""
    engine = PolicyEngine(return_window_days=30, approval_threshold=100.00)
    
    order_date = datetime.now(timezone.utc) - timedelta(days=10)
    result = engine.evaluate_refund_eligibility(
        order_date=order_date,
        order_status="DELIVERED",
        amount=75.00
    )
    
    assert result["is_eligible"] is True
    assert result["requires_approval"] is False
    assert result["error_code"] is None


def test_policy_engine_hitl_approval_required():
    """Test that an order exceeding the $100 threshold triggers supervisor approval."""
    engine = PolicyEngine(return_window_days=30, approval_threshold=100.00)
    
    order_date = datetime.now(timezone.utc) - timedelta(days=5)
    result = engine.evaluate_refund_eligibility(
        order_date=order_date,
        order_status="DELIVERED",
        amount=150.00
    )
    
    assert result["is_eligible"] is True
    assert result["requires_approval"] is True
    assert "PENDING_APPROVAL" in result["reason"]


def test_policy_engine_expired_return_window():
    """Test that an order older than 30 days fails return window validation."""
    engine = PolicyEngine(return_window_days=30, approval_threshold=100.00)
    
    order_date = datetime.now(timezone.utc) - timedelta(days=45)
    result = engine.evaluate_refund_eligibility(
        order_date=order_date,
        order_status="DELIVERED",
        amount=50.00
    )
    
    assert result["is_eligible"] is False
    assert result["error_code"] == "RETURN_WINDOW_EXPIRED"


def test_policy_engine_invalid_status():
    """Test that non-delivered orders (e.g. SHIPPED) are ineligible for refunds."""
    engine = PolicyEngine(return_window_days=30, approval_threshold=100.00)
    
    order_date = datetime.now(timezone.utc) - timedelta(days=2)
    result = engine.evaluate_refund_eligibility(
        order_date=order_date,
        order_status="SHIPPED",
        amount=50.00
    )
    
    assert result["is_eligible"] is False
    assert result["error_code"] == "INVALID_ORDER_STATUS"


def test_idempotency_write_protection(monkeypatch, db_session):
    """Test that duplicate requests with the same idempotency key return the existing record safely."""
    # Seed a test customer and order using SQLite in-memory or patch SessionLocal
    # For simplicity, we seed directly:
    customer = CustomerModel(customer_id="cust_test", email="test@example.com", full_name="Test User")
    order = OrderModel(order_id="ord_test", customer_id="cust_test", status="DELIVERED", total_amount=120.00)
    db_session.add_all([customer, order])
    db_session.commit()

    # Mock SessionLocal in agent/tools to use our test database session
    import agent.tools
    monkeypatch.setattr(agent.tools, "SessionLocal", lambda: db_session)

    idempotency_key = "idemp_key_12345"

    # First call: creates a new refund request
    res1 = create_return_request(
        order_id="ord_test",
        customer_id="cust_test",
        reason="Defective item",
        idempotency_key=idempotency_key
    )
    assert res1["success"] is True
    first_refund_id = res1["data"]["refund_id"]

    # Second call (retry): should detect duplicate via idempotency key and return existing ID
    res2 = create_return_request(
        order_id="ord_test",
        customer_id="cust_test",
        reason="Defective item",
        idempotency_key=idempotency_key
    )
    assert res2["success"] is True
    assert res2["data"]["refund_id"] == first_refund_id
    assert "Duplicate request detected" in res2["message"]
