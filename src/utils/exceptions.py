"""
Custom exception classes for the Gemini Image Generation API.
Provides structured exception hierarchy for better error handling and logging.
"""

from typing import Optional, Dict, Any


class APIBaseError(Exception):
    """Base exception class for all API-related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        status_code: int = 500,
        original_error: Exception = None,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code or "INTERNAL_ERROR"
        self.status_code = status_code
        self.original_error = original_error
        self.context = context or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for JSON response."""
        return {
            "code": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "context": self.context
        }


class ValidationError(APIBaseError):
    """Exception for input validation errors."""
    
    def __init__(
        self,
        message: str,
        field_name: str = None,
        field_value: Any = None,
        original_error: Exception = None
    ):
        context = {}
        if field_name:
            context["field_name"] = field_name
        if field_value is not None:
            context["field_value"] = str(field_value)
        
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=422,
            original_error=original_error,
            context=context
        )
        self.field_name = field_name
        self.field_value = field_value


class GeminiAPIError(APIBaseError):
    """Exception for Gemini API related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        original_error: Exception = None,
        prompt_length: int = None,
        model_name: str = None
    ):
        context = {}
        if prompt_length is not None:
            context["prompt_length"] = prompt_length
        if model_name:
            context["model_name"] = model_name
        
        super().__init__(
            message=message,
            error_code=error_code or "GEMINI_API_ERROR",
            status_code=503,
            original_error=original_error,
            context=context
        )
        self.prompt_length = prompt_length
        self.model_name = model_name


class PromptValidationError(ValidationError):
    """Exception for prompt validation errors."""
    
    def __init__(
        self,
        message: str,
        prompt_length: int = None,
        max_length: int = None,
        original_error: Exception = None
    ):
        context = {}
        if prompt_length is not None:
            context["prompt_length"] = prompt_length
        if max_length is not None:
            context["max_length"] = max_length
        
        super().__init__(
            message=message,
            field_name="prompt",
            field_value=f"length: {prompt_length}" if prompt_length else None,
            original_error=original_error
        )
        self.context.update(context)
        self.prompt_length = prompt_length
        self.max_length = max_length


class S3UploadError(APIBaseError):
    """Exception for S3 upload related errors."""
    
    def __init__(
        self,
        message: str,
        error_code: str = None,
        original_error: Exception = None,
        bucket_name: str = None,
        file_size: int = None,
        s3_key: str = None
    ):
        context = {}
        if bucket_name:
            context["bucket_name"] = bucket_name
        if file_size is not None:
            context["file_size"] = file_size
        if s3_key:
            context["s3_key"] = s3_key
        
        super().__init__(
            message=message,
            error_code=error_code or "S3_UPLOAD_ERROR",
            status_code=502,
            original_error=original_error,
            context=context
        )
        self.bucket_name = bucket_name
        self.file_size = file_size
        self.s3_key = s3_key


class FileSizeError(ValidationError):
    """Exception for file size validation errors."""
    
    def __init__(
        self,
        message: str,
        file_size: int = None,
        max_size: int = None,
        original_error: Exception = None
    ):
        context = {}
        if file_size is not None:
            context["file_size"] = file_size
            context["file_size_mb"] = round(file_size / (1024 * 1024), 2)
        if max_size is not None:
            context["max_size"] = max_size
            context["max_size_mb"] = round(max_size / (1024 * 1024), 2)
        
        super().__init__(
            message=message,
            field_name="file_size",
            field_value=file_size,
            original_error=original_error
        )
        self.context.update(context)
        self.file_size = file_size
        self.max_size = max_size


class ConfigurationError(APIBaseError):
    """Exception for configuration-related errors."""
    
    def __init__(
        self,
        message: str,
        config_key: str = None,
        original_error: Exception = None
    ):
        context = {}
        if config_key:
            context["config_key"] = config_key
        
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500,
            original_error=original_error,
            context=context
        )
        self.config_key = config_key


class AuthenticationError(APIBaseError):
    """Exception for authentication-related errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str = None,
        original_error: Exception = None
    ):
        context = {}
        if service_name:
            context["service_name"] = service_name
        
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401,
            original_error=original_error,
            context=context
        )
        self.service_name = service_name


class RateLimitError(APIBaseError):
    """Exception for rate limiting errors."""
    
    def __init__(
        self,
        message: str,
        retry_after: int = None,
        service_name: str = None,
        original_error: Exception = None
    ):
        context = {}
        if retry_after is not None:
            context["retry_after"] = retry_after
        if service_name:
            context["service_name"] = service_name
        
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_ERROR",
            status_code=429,
            original_error=original_error,
            context=context
        )
        self.retry_after = retry_after
        self.service_name = service_name


class ServiceUnavailableError(APIBaseError):
    """Exception for service unavailability errors."""
    
    def __init__(
        self,
        message: str,
        service_name: str = None,
        retry_after: int = None,
        original_error: Exception = None
    ):
        context = {}
        if service_name:
            context["service_name"] = service_name
        if retry_after is not None:
            context["retry_after"] = retry_after
        
        super().__init__(
            message=message,
            error_code="SERVICE_UNAVAILABLE",
            status_code=503,
            original_error=original_error,
            context=context
        )
        self.service_name = service_name
        self.retry_after = retry_after


# Legacy compatibility - maintain backwards compatibility with existing code
class GeminiAPIException(GeminiAPIError):
    """Legacy alias for GeminiAPIError."""
    pass


class S3UploadException(S3UploadError):
    """Legacy alias for S3UploadError."""
    pass