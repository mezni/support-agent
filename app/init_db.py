import os
from datetime import datetime, timedelta
from app.core.database import engine, Base, SessionLocal
from app.models.database_models import CustomerModel, OrderModel, InvoiceModel

def init_database():
    """Creates database tables and seeds test records."""
    print("Initializing database tables...")
    Base.metadata.create_all(bind=engine)
    
    db = SessionLocal()
    try:
        # Check if sample data already exists
        existing_customer = db.query(CustomerModel).filter_by(customer_id="cust_001").first()
        if existing_customer:
            print("Database already contains seed data. Skipping insertion.")
            return

        print("Seeding test data...")
        
        # 1. Seed Customers
        cust1 = CustomerModel(
            customer_id="cust_001",
            email="alice@example.com",
            full_name="Alice Smith",
            tier="PREMIUM"
        )
        cust2 = CustomerModel(
            customer_id="cust_002",
            email="bob@example.com",
            full_name="Bob Jones",
            tier="STANDARD"
        )
        db.add_all([cust1, cust2])

        # 2. Seed Orders 
        # Order 1: Within the 30-day return window ($150.00 exceeds $100 automated threshold -> triggers HITL)
        order1 = OrderModel(
            order_id="ord_101",
            customer_id="cust_001",
            status="DELIVERED",
            total_amount=150.00,
            currency="USD",
            created_at=datetime.utcnow() - timedelta(days=10)
        )
        
        # Order 2: Outside the 30-day return window ($75.50 is within automated threshold)
        order2 = OrderModel(
            order_id="ord_102",
            customer_id="cust_002",
            status="DELIVERED",
            total_amount=75.50,
            currency="USD",
            created_at=datetime.utcnow() - timedelta(days=45)
        )
        db.add_all([order1, order2])

        # 3. Seed Invoices
        inv1 = InvoiceModel(
            invoice_id="inv_501",
            order_id="ord_101",
            amount=150.00,
            status="PAID"
        )
        inv2 = InvoiceModel(
            invoice_id="inv_502",
            order_id="ord_102",
            amount=75.50,
            status="PAID"
        )
        db.add_all([inv1, inv2])

        db.commit()
        print("Database successfully initialized and seeded with test data!")
        
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    init_database()
