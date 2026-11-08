import uuid
import json
from datetime import datetime, timezone
from typing import Optional, Any, Union, Dict, List
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.database_models import AuditLogModel

class AuditService:
    """
    Service layer responsible for recording immutable audit logs 
    for all tool executions, API requests, and sensitive system actions.
    """

    @staticmethod
    def log_action(
        actor_id: str,
        actor_type: str,
        tool_name: str,
        arguments: Union[Dict[str, Any], List[Any], str],
        outcome: str,
        duration_ms: int,
        db: Optional[Session] = None
    ) -> str:
        """
        Records an immutable audit log entry into the database.
        If a database session is provided, it uses it; otherwise, it opens a short-lived session.
        """
        close_db = False
        if db is None:
            db = SessionLocal()
            close_db = True

        log_id = str(uuid.uuid4())
        
        # Safely serialize arguments or payload to a JSON string
        if isinstance(arguments, (dict, list)):
            try:
                arguments_json = json.dumps(arguments, default=str)
            except Exception:
                arguments_json = str(arguments)
        else:
            arguments_json = str(arguments)

        try:
            audit_record = AuditLogModel(
                log_id=log_id,
                timestamp=datetime.now(timezone.utc),
                actor_id=actor_id,
                actor_type=actor_type,
                tool_name=tool_name,
                arguments_json=arguments_json,
                outcome=outcome,
                duration_ms=duration_ms
            )
            db.add(audit_record)
            db.commit()
            return log_id
        except Exception as e:
            db.rollback()
            # Log failure to stderr/console so compliance issues are immediately visible
            print(f"CRITICAL: Failed to write immutable audit log ({log_id}): {str(e)}")
            return ""
        finally:
            if close_db:
                db.close()

# Singleton instance for dependency injection across middleware and services
audit_service = AuditService()
