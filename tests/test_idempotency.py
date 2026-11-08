import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.database_models import CustomerModel, OrderModel, RefundModel
from app.services.refund_service import refund_service
from agent.tools import create_return_request, issue_refund
import agent.tools


@pytest.fixture(scope="function")
def db_session():
    """Fixture providing an isolated in-memory SQLite database session with seeded test data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    session = TestingSessionLocal()
    
    # Seed initial customer and order records
    customer = CustomerModel(
        customer_id="cust_test_001", 
        email="alice.test@example.com", 
        full_name="Alice Test"
    )
    order = OrderModel(
        order_id="ord_test_001", 
        customer_id="cust_test_001", 
        status="DELIVERED", 
        total_amount=150.00,
        currency="USD"
    )
    session.add_all([customer, order])
    session.commit()
    
    try:
        yield session
    finally:
        session.close()


def test_refund_service_idempotency(db_session):
    """Test that RefundService correctly detects duplicate requests via idempotency key and prevents duplicate writes."""
    idempotency_key = "idemp_key_secure_98765"

    # 1. First transaction request (should create a new record)
    res1 = refund_service.process_refund(
        db=db_session,
        order_id="ord_test_001",
        customer_id="cust_test_001",
        amount=150.00,
        reason="Item defective on arrival",
        idempotency_key=idempotency_key
    )
    
    assert res1["success"] is True
    assert res1["is_duplicate"] is False
    first_refund_id = res1["data"]["refund_id"]

    # 2. Second transaction request with the exact same idempotency key (retry)
    res2 = refund_service.process_refund(
        db=db_session,
        order_id="ord_test_001",
        customer_id="cust_test_001",
        amount=150.00,
        reason="Item defective on arrival",
        idempotency_key=idempotency_key
    )
    
    assert res2["success"] is True
    assert res2["is_duplicate"] is True
    assert res2["data"]["refund_id"] == first_refund_id
    assert "Idempotent retry detected" in res2["message"]

    # 3. Verify that exactly 1 refund record exists in the database table
    total_refunds = db_session.query(RefundModel).count()
    assert total_refunds == 1


def test_tool_layer_idempotency_protection(monkeypatch, db_session):
    """Test that tool-level wrappers (create_return_request & issue_refund) respect idempotency constraints."""
    monkeypatch.setattr(agent.tools, "SessionLocal", lambda: db_session)
    
    test_key = "tool_idemp_key_111222"

    # Call create_return_request for the first time
    response_1 = create_return_request(
        order_id="ord_test_001",
        customer_id="cust_test_001",
        reason="Wrong color received",
        idempotency_key=test_key
    )
    
    assert response_1["success"] is True
    refund_id_1 = response_1["data"]["refund_id"]

    # Call issue_refund with the same idempotency key (simulating network retry)
    response_2 = issue_refund(
        order_id="ord_test_001",
        customer_id="cust_test_001",
        amount=150.00,
        reason="Wrong color received",
        idempotency_key=test_key
    )
    
    assert response_2["success"] is True
    assert response_2["data"]["refund_id"] == refund_id_1
    assert "Idempotent retry detected" in response_2["message"] or "Duplicate request detected" in response_2["message"]
