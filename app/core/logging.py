import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any, Dict

SENSITIVE_KEYS = {
    "password",
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "jwt_secret",
    "authorization",
    "service_role_key",
}


def mask_sensitive_data(data: Any) -> Any:
    if isinstance(data, dict):
        masked = {}
        for k, v in data.items():
            if any(sens in k.lower() for sens in SENSITIVE_KEYS):
                masked[k] = "[REDACTED]"
            elif isinstance(v, (dict, list)):
                masked[k] = mask_sensitive_data(v)
            else:
                masked[k] = v
        return masked
    elif isinstance(data, list):
        return [mask_sensitive_data(item) for item in data]
    return data


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_record: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Extra context
        for key in ["service", "job_id", "lead_id", "campaign_id", "provider", "event", "request_id"]:
            val = getattr(record, key, None)
            if val is not None:
                log_record[key] = val

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        return json.dumps(mask_sensitive_data(log_record))


def setup_logging(service_name: str = "api") -> logging.Logger:
    logger = logging.getLogger("leadgen")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)

    # Attach service attribute
    logger = logging.LoggerAdapter(logger, {"service": service_name})
    return logger  # type: ignore


logger = setup_logging()
