from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, ForeignKey, Text, CheckConstraint, Integer
from sqlalchemy.orm import relationship
from app.core.database import Base

class CustomerModel(Base):
    __tablename__ = "customers"

    customer_id = Column(String(64), primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    tier = Column(String(32), default="STANDARD")
    created_at = Column(DateTime, default=datetime.utcnow)

    orders = relationship("OrderModel", back_populates="customer")
    refunds = relationship("RefundModel", back_populates="customer")


class OrderModel(Base):
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    customer_id = Column(String(64), ForeignKey("customers.customer_id", ondelete="CASCADE"), nullable=False)
    status = Column(String(32), nullable=False)
    total_amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("CustomerModel", back_populates="orders")
    invoices = relationship("InvoiceModel", back_populates="order")
    refunds = relationship("RefundModel", back_populates="order")


class InvoiceModel(Base):
    __tablename__ = "invoices"

    invoice_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), ForeignKey("orders.order_id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    status = Column(String(32), nullable=False)
    issued_at = Column(DateTime, default=datetime.utcnow)

    order = relationship("OrderModel", back_populates="invoices")


class RefundModel(Base):
    __tablename__ = "refunds"

    refund_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), ForeignKey("orders.order_id"), nullable=False)
    customer_id = Column(String(64), ForeignKey("customers.customer_id"), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="USD")
    status = Column(
        String(32),
        CheckConstraint("status IN ('PENDING_APPROVAL', 'APPROVED', 'REJECTED', 'PROCESSING', 'COMPLETED', 'FAILED')"),
        default="PENDING_APPROVAL",
        nullable=False
    )
    idempotency_key = Column(String(128), unique=True, nullable=False, index=True)
    supervisor_id = Column(String(64), nullable=True)
    reason = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    order = relationship("OrderModel", back_populates="refunds")
    customer = relationship("CustomerModel", back_populates="refunds")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    log_id = Column(String(64), primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    actor_id = Column(String(64), nullable=False, index=True)
    actor_type = Column(String(32), nullable=False)
    tool_name = Column(String(128), nullable=False)
    arguments_json = Column(Text, nullable=False)  # Serialized JSON string
    outcome = Column(String(32), nullable=False)
    duration_ms = Column(Integer, nullable=False)
