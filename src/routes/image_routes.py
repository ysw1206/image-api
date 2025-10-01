"""
Image generation API routes.
Handles POST /generate-image endpoint for creating images from text prompts.
"""

import logging
import time
from typing import Dict, Any, List, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from src.services.gemini_client import (
    GeminiImageClient, 
    GeminiAPIError, 
    PromptValidationError,
    ImageGenerationResult
)
from src.services.s3_client import (
    S3UploadClient, 
    S3UploadError, 
    FileSizeError,
    UploadResult
)


# Configure logger
logger = logging.getLogger(__name__)

# Create API router
router = APIRouter(prefix="/api/v1", tags=["Image Generation"])


class ImageGenerationRequest(BaseModel):
    """Request model for image generation."""
    
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=480,
        description="Text prompt for image generation (1-480 characters)",
        example="A beautiful sunset over snow-capped mountains with a lake reflection"
    )
    
    number_of_images: int = Field(
        default=1,
        ge=1,
        le=4,
        description="Number of images to generate (1-4)",
        example=1
    )
    
    image_size: str = Field(
        default="1K",
        description="Size of generated images",
        example="1K"
    )
    
    aspect_ratio: str = Field(
        default="1:1",
        description="Aspect ratio of generated images",
        example="1:1"
    )
    
    @validator("prompt")
    def validate_prompt_content(cls, v):
        """Validate prompt content for safety."""
        v = v.strip()
        if not v:
            raise ValueError("Prompt cannot be empty or whitespace only")
        
        # Basic content filtering (can be extended)
        forbidden_words = ["nsfw", "explicit", "violent"]
        lower_prompt = v.lower()
        for word in forbidden_words:
            if word in lower_prompt:
                raise ValueError(f"Prompt contains forbidden content: {word}")
        
        return v
    
    @validator("image_size")
    def validate_image_size(cls, v):
        """Validate image size parameter."""
        allowed_sizes = ["1K", "2K"]
        if v not in allowed_sizes:
            raise ValueError(f"Image size must be one of: {', '.join(allowed_sizes)}")
        return v
    
    @validator("aspect_ratio")
    def validate_aspect_ratio(cls, v):
        """Validate aspect ratio parameter."""
        allowed_ratios = ["1:1", "3:4", "4:3", "9:16", "16:9"]
        if v not in allowed_ratios:
            raise ValueError(f"Aspect ratio must be one of: {', '.join(allowed_ratios)}")
        return v


class GeneratedImage(BaseModel):
    """Model for a single generated image."""
    
    url: str = Field(
        ...,
        description="Public URL of the generated image",
        example="https://bucket.s3.region.amazonaws.com/images/20241201_120000/uuid.jpg"
    )
    
    filename: str = Field(
        ...,
        description="Generated filename in S3",
        example="images/20241201_120000/12345678-1234-5678-abcd-123456789abc.jpg"
    )
    
    size: int = Field(
        ...,
        description="File size in bytes",
        example=1048576
    )
    
    generation_time: float = Field(
        ...,
        description="Time taken to generate this image in seconds",
        example=2.5
    )


class ImageGenerationResponse(BaseModel):
    """Response model for successful image generation."""
    
    success: bool = Field(
        default=True,
        description="Whether the request was successful"
    )
    
    data: Dict[str, Any] = Field(
        ...,
        description="Response data containing generated images"
    )
    
    message: str = Field(
        ...,
        description="Success message",
        example="Images generated successfully"
    )
    
    metadata: Dict[str, Any] = Field(
        ...,
        description="Additional metadata about the generation process"
    )


# Initialize clients (singleton pattern)
gemini_client = None
s3_client = None


def get_gemini_client() -> GeminiImageClient:
    """Get or create Gemini client instance."""
    global gemini_client
    if gemini_client is None:
        gemini_client = GeminiImageClient()
    return gemini_client


def get_s3_client() -> S3UploadClient:
    """Get or create S3 client instance."""
    global s3_client
    if s3_client is None:
        s3_client = S3UploadClient()
    return s3_client


@router.post(
    "/generate-image",
    response_model=ImageGenerationResponse,
    summary="Generate images from text prompt",
    description="Generate one or more images from a text description using Gemini AI and upload to S3",
    responses={
        200: {
            "description": "Images generated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "data": {
                            "images": [
                                {
                                    "url": "https://bucket.s3.region.amazonaws.com/images/20241201_120000/uuid.jpg",
                                    "filename": "images/20241201_120000/uuid.jpg",
                                    "size": 1048576,
                                    "generation_time": 2.5
                                }
                            ],
                            "total_images": 1
                        },
                        "message": "Images generated successfully",
                        "metadata": {
                            "prompt": "A beautiful sunset",
                            "model_used": "imagen-4.0-generate-001",
                            "total_processing_time": 3.2,
                            "request_id": "req_12345"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request parameters",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Request validation failed",
                        "error": {
                            "code": "VALIDATION_ERROR",
                            "details": "Prompt cannot be empty"
                        }
                    }
                }
            }
        },
        500: {
            "description": "Server error during image generation",
            "content": {
                "application/json": {
                    "example": {
                        "success": False,
                        "data": None,
                        "message": "Image generation failed",
                        "error": {
                            "code": "GENERATION_ERROR",
                            "details": "Failed to generate image with Gemini API"
                        }
                    }
                }
            }
        }
    }
)
async def generate_image(
    request: ImageGenerationRequest,
    http_request: Request
) -> Dict[str, Any]:
    """
    Generate images from text prompt using Gemini AI and upload to S3.
    
    This endpoint:
    1. Validates the input prompt and parameters
    2. Generates images using Google Gemini Imagen API
    3. Uploads generated images to AWS S3
    4. Returns public URLs and metadata
    
    Args:
        request: Image generation request with prompt and options
        http_request: FastAPI request object for logging
        
    Returns:
        Dict containing generated image URLs and metadata
        
    Raises:
        HTTPException: For validation errors (400) or server errors (500)
    """
    start_time = time.time()
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.info(f"🎨 Starting image generation request {request_id}")
    logger.info(f"   Prompt: '{request.prompt[:50]}...' ({len(request.prompt)} chars)")
    logger.info(f"   Parameters: {request.number_of_images} images, {request.image_size}, {request.aspect_ratio}")
    logger.info(f"   Client IP: {http_request.client.host if http_request.client else 'unknown'}")
    
    try:
        # Get service clients
        gemini = get_gemini_client()
        s3 = get_s3_client()
        
        # Prepare generation config
        from google.genai import types
        generation_config = types.GenerateImagesConfig(
            number_of_images=request.number_of_images,
            image_size=request.image_size,
            aspect_ratio=request.aspect_ratio
        )
        
        # Generate images with Gemini
        logger.info(f"🤖 Generating {request.number_of_images} image(s) with Gemini...")
        generation_start = time.time()
        
        generated_images: List[ImageGenerationResult] = await gemini.generate_image(
            prompt=request.prompt,
            config=generation_config
        )
        
        generation_time = time.time() - generation_start
        logger.info(f"✅ Image generation completed in {generation_time:.2f}s")
        
        # Upload images to S3
        upload_start = time.time()
        uploaded_images = []
        
        for i, image_result in enumerate(generated_images):
            logger.info(f"☁️  Uploading image {i+1}/{len(generated_images)} to S3...")
            
            # Generate filename based on prompt (first few words)
            prompt_words = request.prompt.split()[:3]
            base_filename = "_".join(prompt_words).lower().replace(" ", "_")
            filename = f"{base_filename}_{i+1}.png"
            
            # Upload to S3
            upload_result: UploadResult = await s3.upload_image(
                image_data=image_result.image_data,
                filename=filename,
                content_type=image_result.mime_type
            )
            
            # Create response image object
            image_info = {
                "url": upload_result.public_url,
                "filename": upload_result.s3_key,
                "size": upload_result.file_size,
                "generation_time": image_result.generation_time
            }
            
            uploaded_images.append(image_info)
            logger.info(f"✅ Image {i+1} uploaded: {upload_result.public_url}")
        
        upload_time = time.time() - upload_start
        total_time = time.time() - start_time
        
        # Prepare response
        response_data = {
            "success": True,
            "data": {
                "images": uploaded_images,
                "total_images": len(uploaded_images)
            },
            "message": f"Successfully generated {len(uploaded_images)} image(s)",
            "metadata": {
                "prompt": request.prompt,
                "model_used": gemini.MODEL_NAME,
                "generation_time": round(generation_time, 2),
                "upload_time": round(upload_time, 2),
                "total_processing_time": round(total_time, 2),
                "request_id": request_id,
                "parameters": {
                    "number_of_images": request.number_of_images,
                    "image_size": request.image_size,
                    "aspect_ratio": request.aspect_ratio
                }
            }
        }
        
        logger.info(f"🎉 Request {request_id} completed successfully in {total_time:.2f}s")
        return response_data
        
    except PromptValidationError as e:
        logger.warning(f"❌ Prompt validation error for request {request_id}: {e.message}")
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "data": None,
                "message": "Invalid prompt",
                "error": {
                    "code": "PROMPT_VALIDATION_ERROR",
                    "details": e.message
                }
            }
        )
        
    except GeminiAPIError as e:
        logger.error(f"❌ Gemini API error for request {request_id}: {e.message}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "data": None,
                "message": "Image generation failed",
                "error": {
                    "code": e.error_code or "GEMINI_API_ERROR",
                    "details": e.message
                }
            }
        )
        
    except (S3UploadError, FileSizeError) as e:
        logger.error(f"❌ S3 upload error for request {request_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "data": None,
                "message": "Image upload failed",
                "error": {
                    "code": getattr(e, 'error_code', 'S3_UPLOAD_ERROR'),
                    "details": str(e)
                }
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Unexpected error for request {request_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "data": None,
                "message": "Internal server error",
                "error": {
                    "code": "INTERNAL_ERROR",
                    "details": "An unexpected error occurred during image generation"
                }
            }
        )


@router.get(
    "/generate-image/info",
    summary="Get image generation service information",
    description="Get information about the image generation service capabilities and limits"
)
async def get_generation_info() -> Dict[str, Any]:
    """
    Get information about the image generation service.
    
    Returns:
        Dict containing service capabilities and limits
    """
    try:
        gemini = get_gemini_client()
        s3 = get_s3_client()
        
        return {
            "success": True,
            "data": {
                "service": "Gemini Image Generation API",
                "version": "1.0.0",
                "gemini_info": gemini.get_client_info(),
                "s3_info": s3.get_client_info(),
                "supported_operations": [
                    "Text-to-image generation",
                    "Multiple image generation (1-4 images)",
                    "Various aspect ratios and sizes",
                    "Automatic S3 upload and public URL generation"
                ]
            },
            "message": "Service information retrieved successfully"
        }
        
    except Exception as e:
        logger.error(f"❌ Error getting service info: {e}")
        raise HTTPException(
            status_code=500,
            detail={
                "success": False,
                "data": None,
                "message": "Failed to retrieve service information",
                "error": {
                    "code": "SERVICE_INFO_ERROR",
                    "details": str(e)
                }
            }
        )