from fastapi import FastAPI
from app.api.endpoints import router as api_router
from app.api.middleware import AuditLoggingMiddleware

app = FastAPI(
    title="Customer Support AI Agent API",
    version="1.0.0",
    description="Production-grade support agent with policy enforcement and audit logging."
)

# Register audit logging middleware
app.add_middleware(AuditLoggingMiddleware)

# Include API routes
app.include_router(api_router)

@app.get("/")
def health_check():
    return {"status": "healthy", "service": "support-agent"}
