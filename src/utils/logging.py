"""
Structured logging system for the Gemini Image Generation API.
Provides JSON-formatted logging with request tracking and context management.
"""

import json
import logging
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from contextvars import ContextVar
from pathlib import Path

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


# Context variables for request tracking
request_id_var: ContextVar[str] = ContextVar('request_id', default='')
user_id_var: ContextVar[str] = ContextVar('user_id', default='')


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured JSON logging."""
    
    def __init__(self, service_name: str = "image-api"):
        super().__init__()
        self.service_name = service_name
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        # Get request context
        request_id = request_id_var.get('')
        user_id = user_id_var.get('')
        
        # Build base log structure
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service_name,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add request context if available
        if request_id:
            log_data["request_id"] = request_id
        if user_id:
            log_data["user_id"] = user_id
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": self.formatException(record.exc_info) if record.exc_info else None
            }
        
        # Add extra fields from the log record
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'getMessage'
            }:
                extra_fields[key] = value
        
        if extra_fields:
            log_data["extra"] = extra_fields
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware for logging HTTP requests and responses with structured format."""
    
    def __init__(self, app, logger_name: str = "image-api.requests"):
        super().__init__(app)
        self.logger = logging.getLogger(logger_name)
    
    async def dispatch(self, request: Request, call_next):
        """Process request and log details."""
        # Generate unique request ID
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        # Extract user identification if available (from headers, auth, etc.)
        user_id = request.headers.get('X-User-ID', '')
        if user_id:
            user_id_var.set(user_id)
        
        # Record request start time
        start_time = time.time()
        
        # Extract request details
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get('user-agent', '')
        
        # Log incoming request
        self.logger.info(
            f"Incoming request: {request.method} {request.url.path}",
            extra={
                "request": {
                    "method": request.method,
                    "url": str(request.url),
                    "path": request.url.path,
                    "query_params": dict(request.query_params),
                    "headers": dict(request.headers),
                    "client_ip": client_ip,
                    "user_agent": user_agent
                },
                "event_type": "request_start"
            }
        )
        
        # Process request
        try:
            response = await call_next(request)
            
            # Calculate processing time
            processing_time = time.time() - start_time
            
            # Log successful response
            self.logger.info(
                f"Request completed: {request.method} {request.url.path} - {response.status_code}",
                extra={
                    "response": {
                        "status_code": response.status_code,
                        "headers": dict(response.headers),
                        "processing_time_ms": round(processing_time * 1000, 2)
                    },
                    "event_type": "request_complete"
                }
            )
            
            # Add request ID to response headers for tracing
            response.headers["X-Request-ID"] = request_id
            
            return response
            
        except Exception as e:
            # Calculate processing time for failed requests
            processing_time = time.time() - start_time
            
            # Log failed request
            self.logger.error(
                f"Request failed: {request.method} {request.url.path} - {str(e)}",
                extra={
                    "error": {
                        "type": type(e).__name__,
                        "message": str(e),
                        "processing_time_ms": round(processing_time * 1000, 2)
                    },
                    "event_type": "request_error"
                },
                exc_info=True
            )
            
            # Re-raise the exception to be handled by FastAPI
            raise
        finally:
            # Clear context variables
            request_id_var.set('')
            user_id_var.set('')
    
    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP address from request."""
        # Check for forwarded IP headers (in order of preference)
        forwarded_headers = [
            'X-Forwarded-For',
            'X-Real-IP',
            'X-Client-IP',
            'CF-Connecting-IP'  # Cloudflare
        ]
        
        for header in forwarded_headers:
            ip = request.headers.get(header)
            if ip:
                # X-Forwarded-For can contain multiple IPs, take the first one
                return ip.split(',')[0].strip()
        
        # Fallback to direct client IP
        if hasattr(request.client, 'host'):
            return request.client.host
        
        return 'unknown'


class StructuredLogger:
    """Enhanced logger with structured logging capabilities."""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_api_call(
        self,
        service: str,
        operation: str,
        duration_ms: float = None,
        success: bool = True,
        extra_data: Dict[str, Any] = None
    ):
        """Log API call with structured data."""
        log_data = {
            "service": service,
            "operation": operation,
            "success": success,
            "event_type": "api_call"
        }
        
        if duration_ms is not None:
            log_data["duration_ms"] = round(duration_ms, 2)
        
        if extra_data:
            log_data.update(extra_data)
        
        level = logging.INFO if success else logging.ERROR
        message = f"API call: {service}.{operation} - {'SUCCESS' if success else 'FAILED'}"
        
        self.logger.log(level, message, extra=log_data)
    
    def log_performance(
        self,
        operation: str,
        duration_ms: float,
        metadata: Dict[str, Any] = None
    ):
        """Log performance metrics."""
        log_data = {
            "operation": operation,
            "duration_ms": round(duration_ms, 2),
            "event_type": "performance"
        }
        
        if metadata:
            log_data["metadata"] = metadata
        
        self.logger.info(
            f"Performance: {operation} completed in {duration_ms:.2f}ms",
            extra=log_data
        )
    
    def log_business_event(
        self,
        event_name: str,
        event_data: Dict[str, Any] = None,
        user_id: str = None
    ):
        """Log business events for analytics."""
        log_data = {
            "event_name": event_name,
            "event_type": "business_event"
        }
        
        if event_data:
            log_data["event_data"] = event_data
        
        if user_id:
            log_data["user_id"] = user_id
        
        self.logger.info(f"Business event: {event_name}", extra=log_data)


def setup_structured_logging(
    service_name: str = "image-api",
    log_level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure structured logging for the application.
    
    Args:
        service_name: Name of the service for logging context
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for file logging
    
    Returns:
        logging.Logger: Configured root logger
    """
    # Create formatter
    formatter = StructuredFormatter(service_name=service_name)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    root_logger.addHandler(console_handler)
    
    # File handler (if specified)
    if log_file:
        # Ensure log directory exists
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        root_logger.addHandler(file_handler)
    
    # Suppress verbose third-party loggers
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    
    # Get application logger
    app_logger = logging.getLogger(service_name)
    app_logger.info(f"Structured logging configured - Level: {log_level}, Service: {service_name}")
    
    return app_logger


def get_structured_logger(name: str) -> StructuredLogger:
    """Get a structured logger instance."""
    return StructuredLogger(name)


def get_request_id() -> str:
    """Get current request ID from context."""
    return request_id_var.get('')


def set_request_context(request_id: str, user_id: str = ''):
    """Set request context variables."""
    request_id_var.set(request_id)
    if user_id:
        user_id_var.set(user_id)