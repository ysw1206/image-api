"""
FastAPI application entry point for the Gemini Image Generation API.
Handles server initialization, middleware configuration, and health check endpoints.
"""

import logging
import sys
from datetime import datetime
from typing import Dict, Any

import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from src.config import get_settings, validate_settings
from src.routes.image_routes import router as image_router
from src.utils.logging import setup_structured_logging, RequestLoggingMiddleware, get_structured_logger
from src.utils.exceptions import (
    APIBaseError,
    ValidationError,
    GeminiAPIError,
    S3UploadError,
    ConfigurationError,
    AuthenticationError,
    RateLimitError,
    ServiceUnavailableError
)


# Configure structured logging
def setup_logging():
    """Configure structured JSON logging for the application."""
    settings = get_settings()
    
    # Setup structured logging
    logger = setup_structured_logging(
        service_name="image-api",
        log_level=settings.log_level,
        log_file=None  # Can be configured to write to file if needed
    )
    
    return logger


# Initialize FastAPI app
app = FastAPI(
    title="Gemini Image Generation API",
    description="RESTful API for generating images using Google Gemini AI and storing them on AWS S3",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Setup logging
logger = setup_logging()


@app.on_event("startup")
async def startup_event():
    """Application startup event handler."""
    logger.info("🚀 Starting Gemini Image Generation API...")
    
    try:
        # Validate configuration on startup
        validate_settings()
        logger.info("✅ Configuration validation successful")
        
        # Log startup information
        settings = get_settings()
        logger.info(f"🌍 Environment: {settings.environment}")
        logger.info(f"🔧 AWS Region: {settings.aws_region}")
        logger.info(f"📦 S3 Bucket: {settings.s3_bucket_name}")
        logger.info(f"🚀 Server starting on port: {settings.port}")
        
    except Exception as e:
        logger.error(f"❌ Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event handler."""
    logger.info("🛑 Shutting down Gemini Image Generation API...")


# Configure CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)

# Include API routes
app.include_router(image_router)


# Global exception handlers
@app.exception_handler(APIBaseError)
async def api_base_exception_handler(request: Request, exc: APIBaseError):
    """Handle custom API exceptions with structured logging."""
    structured_logger = get_structured_logger("image-api.exceptions")
    
    # Log the exception with context
    structured_logger.logger.error(
        f"API Error: {exc.error_code} - {exc.message}",
        extra={
            "error": exc.to_dict(),
            "request": {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path
            },
            "event_type": "api_error"
        },
        exc_info=exc.original_error if exc.original_error else None
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.message,
            "error": {
                "code": exc.error_code,
                "details": exc.message,
                "context": exc.context
            }
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with consistent response format."""
    structured_logger = get_structured_logger("image-api.exceptions")
    
    structured_logger.logger.warning(
        f"HTTP {exc.status_code}: {exc.detail}",
        extra={
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail,
                "status_code": exc.status_code
            },
            "request": {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path
            },
            "event_type": "http_error"
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "data": None,
            "message": exc.detail,
            "error": {
                "code": f"HTTP_{exc.status_code}",
                "details": exc.detail
            }
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors with detailed information."""
    structured_logger = get_structured_logger("image-api.exceptions")
    
    structured_logger.logger.warning(
        "Request validation failed",
        extra={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors()
            },
            "request": {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path
            },
            "event_type": "validation_error"
        }
    )
    
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "data": None,
            "message": "Request validation failed",
            "error": {
                "code": "VALIDATION_ERROR",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with proper logging."""
    structured_logger = get_structured_logger("image-api.exceptions")
    
    structured_logger.logger.error(
        f"Unexpected error: {str(exc)}",
        extra={
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred",
                "type": type(exc).__name__,
                "details": str(exc)
            },
            "request": {
                "method": request.method,
                "url": str(request.url),
                "path": request.url.path
            },
            "event_type": "unexpected_error"
        },
        exc_info=True
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "message": "Internal server error",
            "error": {
                "code": "INTERNAL_ERROR",
                "details": "An unexpected error occurred"
            }
        }
    )


# Health check endpoint
@app.get("/healthz", tags=["Health"])
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint to verify service status.
    
    Returns:
        Dict[str, Any]: Health status with timestamp
        
    Example:
        GET /healthz
        
        Response:
        {
            "status": "healthy",
            "timestamp": "2024-01-01T12:00:00.000000Z",
            "version": "1.0.0",
            "environment": "development"
        }
    """
    settings = get_settings()
    
    health_data = {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "version": "1.0.0",
        "environment": settings.environment
    }
    
    logger.info("Health check requested")
    return health_data


# Root endpoint with API information
@app.get("/", tags=["Info"])
async def root() -> Dict[str, Any]:
    """
    Root endpoint with API information.
    
    Returns:
        Dict[str, Any]: API information
    """
    return {
        "name": "Gemini Image Generation API",
        "version": "1.0.0",
        "description": "RESTful API for generating images using Google Gemini AI",
        "docs_url": "/docs",
        "health_check": "/healthz"
    }


if __name__ == "__main__":
    """Run the application with uvicorn when executed directly."""
    settings = get_settings()
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
        access_log=True
    )