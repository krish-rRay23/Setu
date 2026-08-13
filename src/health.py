from typing import Dict, Any
from datetime import datetime, timezone

def check_system_health(session_factory=None) -> Dict[str, Any]:
    status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "components": {
            "database": "unknown",
            "classifier": "ready",
            "policy_engine": "ready"
        }
    }
    if session_factory:
        try:
            with session_factory() as session:
                session.execute("SELECT 1")
                status["components"]["database"] = "healthy"
        except Exception as e:
            status["components"]["database"] = f"unhealthy: {str(e)}"
            status["status"] = "degraded"
    else:
        status["components"]["database"] = "unconfigured"

    return status
