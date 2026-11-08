import time
import uuid
import json
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.core.database import SessionLocal
from app.models.database_models import AuditLogModel

class AuditLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Extract actor context from headers or default to anonymous/system
        actor_id = request.headers.get("X-Actor-ID", "system_agent")
        actor_type = request.headers.get("X-Actor-Type", "LLM_AGENT")
        tool_name = request.url.path
        
        response = await call_next(request)
        
        duration_ms = int((time.time() - start_time) * 1000)
        outcome = "SUCCESS" if response.status_code < 400 else "ERROR"
        
        # Capture request body summary (redacted for PII if necessary)
        try:
            body_bytes = await request.body()
            arguments_json = body_bytes.decode("utf-8") if body_bytes else "{}"
        except Exception:
            arguments_json = "{}"

        # Write immutable audit log record to SQLite
        db = SessionLocal()
        try:
            audit_log = AuditLogModel(
                log_id=str(uuid.uuid4()),
                actor_id=actor_id,
                actor_type=actor_type,
                tool_name=tool_name,
                arguments_json=arguments_json,
                outcome=outcome,
                duration_ms=duration_ms
            )
            db.add(audit_log)
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Failed to write audit log: {e}")
        finally:
            db.close()

        return response
