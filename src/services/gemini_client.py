"""
Gemini API client service for image generation.
Handles integration with Google Gemini Imagen API for text-to-image generation.
"""

import asyncio
import logging
import time
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from google import genai
from google.genai import types

from src.config import get_settings


# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class ImageGenerationResult:
    """Result from image generation containing image data and metadata."""
    image_data: bytes
    mime_type: str
    size: int
    generation_time: float
    model_used: str


class GeminiAPIError(Exception):
    """Custom exception for Gemini API related errors."""
    def __init__(self, message: str, error_code: str = None, original_error: Exception = None):
        self.message = message
        self.error_code = error_code
        self.original_error = original_error
        super().__init__(self.message)


class PromptValidationError(Exception):
    """Custom exception for prompt validation errors."""
    def __init__(self, message: str, prompt_length: int = None):
        self.message = message
        self.prompt_length = prompt_length
        super().__init__(self.message)


class GeminiImageClient:
    """
    Client for Google Gemini Imagen API image generation.
    
    Provides async methods for generating images from text prompts
    with comprehensive error handling and logging.
    """
    
    def __init__(self):
        """Initialize Gemini client with API key from settings."""
        self.settings = get_settings()
        self.client = None
        self._initialize_client()
        
        # Configuration constants
        self.MODEL_NAME = "imagen-4.0-generate-001"
        self.MAX_PROMPT_LENGTH = 480  # tokens
        self.MAX_IMAGES = 4
        self.SUPPORTED_IMAGE_SIZES = ["1K", "2K"]
        self.SUPPORTED_ASPECT_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9"]
        
        logger.info(f"Gemini Image Client initialized with model: {self.MODEL_NAME}")
    
    def _initialize_client(self):
        """Initialize the Gemini client with proper error handling."""
        try:
            # Configure the client with API key
            self.client = genai.Client(api_key=self.settings.gemini_api_key)
            logger.info("✅ Gemini client initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Gemini client: {e}")
            raise GeminiAPIError(
                "Failed to initialize Gemini client. Please check your API key.",
                error_code="INITIALIZATION_ERROR",
                original_error=e
            )
    
    def _validate_prompt(self, prompt: str) -> None:
        """
        Validate the input prompt for image generation.
        
        Args:
            prompt: The text prompt for image generation
            
        Raises:
            PromptValidationError: If prompt is invalid
        """
        if not prompt or not prompt.strip():
            raise PromptValidationError("Prompt cannot be empty or whitespace only")
        
        # Basic length validation (approximate token count)
        prompt_length = len(prompt.split())
        if prompt_length > self.MAX_PROMPT_LENGTH:
            raise PromptValidationError(
                f"Prompt too long. Maximum {self.MAX_PROMPT_LENGTH} tokens allowed, got approximately {prompt_length} tokens",
                prompt_length=prompt_length
            )
        
        # Check for potentially problematic content
        if len(prompt.strip()) < 3:
            raise PromptValidationError("Prompt too short. Please provide a more descriptive prompt")
    
    def _validate_config(self, config: Optional[types.GenerateImagesConfig]) -> None:
        """
        Validate the image generation configuration.
        
        Args:
            config: Configuration for image generation
            
        Raises:
            PromptValidationError: If configuration is invalid
        """
        if config is None:
            return
        
        if hasattr(config, 'number_of_images') and config.number_of_images:
            if not (1 <= config.number_of_images <= self.MAX_IMAGES):
                raise PromptValidationError(
                    f"Number of images must be between 1 and {self.MAX_IMAGES}, got {config.number_of_images}"
                )
        
        if hasattr(config, 'image_size') and config.image_size:
            if config.image_size not in self.SUPPORTED_IMAGE_SIZES:
                raise PromptValidationError(
                    f"Image size must be one of {self.SUPPORTED_IMAGE_SIZES}, got {config.image_size}"
                )
        
        if hasattr(config, 'aspect_ratio') and config.aspect_ratio:
            if config.aspect_ratio not in self.SUPPORTED_ASPECT_RATIOS:
                raise PromptValidationError(
                    f"Aspect ratio must be one of {self.SUPPORTED_ASPECT_RATIOS}, got {config.aspect_ratio}"
                )
    
    async def generate_image(
        self,
        prompt: str,
        config: Optional[types.GenerateImagesConfig] = None
    ) -> List[ImageGenerationResult]:
        """
        Generate images from text prompt using Gemini Imagen API.
        
        Args:
            prompt: Text description for image generation
            config: Optional configuration for image generation
            
        Returns:
            List[ImageGenerationResult]: Generated images with metadata
            
        Raises:
            PromptValidationError: If prompt or config is invalid
            GeminiAPIError: If API call fails
        """
        start_time = time.time()
        
        try:
            # Validate inputs
            self._validate_prompt(prompt)
            self._validate_config(config)
            
            # Use default config if none provided
            if config is None:
                config = types.GenerateImagesConfig(number_of_images=1)
            
            logger.info(f"🎨 Generating image with prompt: '{prompt[:50]}...' (length: {len(prompt.split())} tokens)")
            logger.info(f"📊 Config: {config}")
            
            # Make API call in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.client.models.generate_images(
                    model=self.MODEL_NAME,
                    prompt=prompt,
                    config=config
                )
            )
            
            generation_time = time.time() - start_time
            
            # Process response
            if not response or not hasattr(response, 'images') or not response.images:
                raise GeminiAPIError(
                    "No images generated. The API returned an empty response.",
                    error_code="EMPTY_RESPONSE"
                )
            
            results = []
            for i, image in enumerate(response.images):
                try:
                    # Extract image data
                    if hasattr(image, 'data'):
                        image_data = image.data
                    elif hasattr(image, 'bytes'):
                        image_data = image.bytes
                    else:
                        # Try to get image data from different possible attributes
                        image_data = getattr(image, '_data', None) or getattr(image, '_bytes', None)
                        if image_data is None:
                            raise GeminiAPIError(
                                f"Could not extract image data from response for image {i+1}",
                                error_code="DATA_EXTRACTION_ERROR"
                            )
                    
                    if not image_data:
                        raise GeminiAPIError(
                            f"Empty image data received for image {i+1}",
                            error_code="EMPTY_IMAGE_DATA"
                        )
                    
                    # Create result object
                    result = ImageGenerationResult(
                        image_data=image_data,
                        mime_type="image/png",  # Gemini typically returns PNG
                        size=len(image_data),
                        generation_time=generation_time,
                        model_used=self.MODEL_NAME
                    )
                    
                    results.append(result)
                    logger.info(f"✅ Image {i+1} processed: {len(image_data)} bytes")
                
                except Exception as e:
                    logger.error(f"❌ Error processing image {i+1}: {e}")
                    raise GeminiAPIError(
                        f"Failed to process generated image {i+1}: {str(e)}",
                        error_code="IMAGE_PROCESSING_ERROR",
                        original_error=e
                    )
            
            logger.info(f"✅ Successfully generated {len(results)} image(s) in {generation_time:.2f}s")
            return results
            
        except PromptValidationError:
            # Re-raise validation errors as-is
            raise
            
        except GeminiAPIError:
            # Re-raise our custom API errors as-is
            raise
            
        except Exception as e:
            logger.error(f"❌ Unexpected error during image generation: {e}", exc_info=True)
            raise GeminiAPIError(
                f"Unexpected error during image generation: {str(e)}",
                error_code="UNEXPECTED_ERROR",
                original_error=e
            )
    
    async def generate_single_image(
        self,
        prompt: str,
        image_size: str = "1K",
        aspect_ratio: str = "1:1"
    ) -> ImageGenerationResult:
        """
        Convenience method to generate a single image with common parameters.
        
        Args:
            prompt: Text description for image generation
            image_size: Size of the image ("1K" or "2K")
            aspect_ratio: Aspect ratio of the image
            
        Returns:
            ImageGenerationResult: Single generated image with metadata
            
        Raises:
            PromptValidationError: If inputs are invalid
            GeminiAPIError: If API call fails
        """
        config = types.GenerateImagesConfig(
            number_of_images=1,
            image_size=image_size,
            aspect_ratio=aspect_ratio
        )
        
        results = await self.generate_image(prompt, config)
        
        if not results:
            raise GeminiAPIError(
                "No image generated from single image request",
                error_code="EMPTY_SINGLE_RESULT"
            )
        
        return results[0]
    
    def get_client_info(self) -> Dict[str, Any]:
        """
        Get information about the client configuration.
        
        Returns:
            Dict[str, Any]: Client configuration information
        """
        return {
            "model_name": self.MODEL_NAME,
            "max_prompt_length": self.MAX_PROMPT_LENGTH,
            "max_images": self.MAX_IMAGES,
            "supported_image_sizes": self.SUPPORTED_IMAGE_SIZES,
            "supported_aspect_ratios": self.SUPPORTED_ASPECT_RATIOS,
            "client_initialized": self.client is not None
        }