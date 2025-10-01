"""
S3 upload client service for image storage.
Handles secure upload of images to AWS S3 with public URL generation.
"""

import asyncio
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass
import mimetypes
import hashlib

import boto3
from botocore.exceptions import ClientError, NoCredentialsError, PartialCredentialsError

from src.config import get_settings


# Configure logger
logger = logging.getLogger(__name__)


@dataclass
class UploadResult:
    """Result from S3 upload containing file information and metadata."""
    public_url: str
    s3_key: str
    bucket_name: str
    file_size: int
    mime_type: str
    upload_time: float
    etag: str


class S3UploadError(Exception):
    """Custom exception for S3 upload related errors."""
    def __init__(self, message: str, error_code: str = None, original_error: Exception = None):
        self.message = message
        self.error_code = error_code
        self.original_error = original_error
        super().__init__(self.message)


class FileSizeError(Exception):
    """Custom exception for file size validation errors."""
    def __init__(self, message: str, file_size: int = None, max_size: int = None):
        self.message = message
        self.file_size = file_size
        self.max_size = max_size
        super().__init__(self.message)


class S3UploadClient:
    """
    Client for uploading images to AWS S3 with security features.
    
    Provides async methods for secure image upload with unique filename generation,
    file size validation, and public URL generation.
    """
    
    def __init__(self):
        """Initialize S3 client with AWS credentials from settings."""
        self.settings = get_settings()
        self.s3_client = None
        self._initialize_client()
        
        # Configuration constants
        self.MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB as per shrimp-rules.md
        self.ALLOWED_MIME_TYPES = {
            'image/jpeg', 'image/jpg', 'image/png', 'image/gif', 'image/webp'
        }
        self.IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
        
        logger.info(f"S3 Upload Client initialized for bucket: {self.settings.s3_bucket_name}")
    
    def _initialize_client(self):
        """Initialize the S3 client with proper error handling."""
        try:
            # Initialize S3 client with explicit credentials
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=self.settings.aws_access_key_id,
                aws_secret_access_key=self.settings.aws_secret_access_key,
                region_name=self.settings.aws_region
            )
            
            # Test connectivity by checking bucket access (sync version for init)
            try:
                self.s3_client.head_bucket(Bucket=self.settings.s3_bucket_name)
                logger.info(f"✅ Bucket access confirmed: {self.settings.s3_bucket_name}")
            except ClientError as e:
                error_code = e.response['Error']['Code']
                if error_code == '404':
                    raise S3UploadError(
                        f"S3 bucket '{self.settings.s3_bucket_name}' not found",
                        error_code="BUCKET_NOT_FOUND",
                        original_error=e
                    )
                elif error_code == '403':
                    raise S3UploadError(
                        f"Access denied to S3 bucket '{self.settings.s3_bucket_name}'",
                        error_code="BUCKET_ACCESS_DENIED",
                        original_error=e
                    )
                else:
                    raise S3UploadError(
                        f"Cannot access S3 bucket: {e}",
                        error_code="BUCKET_ACCESS_ERROR",
                        original_error=e
                    )
            
            logger.info("✅ S3 client initialized successfully")
            
        except (NoCredentialsError, PartialCredentialsError) as e:
            logger.error(f"❌ AWS credentials error: {e}")
            raise S3UploadError(
                "Invalid AWS credentials. Please check your access key and secret key.",
                error_code="CREDENTIALS_ERROR",
                original_error=e
            )
        except Exception as e:
            logger.error(f"❌ Failed to initialize S3 client: {e}")
            raise S3UploadError(
                f"Failed to initialize S3 client: {str(e)}",
                error_code="INITIALIZATION_ERROR",
                original_error=e
            )
    
    async def _test_bucket_access(self):
        """Test if the bucket is accessible."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.head_bucket(Bucket=self.settings.s3_bucket_name)
            )
            logger.info(f"✅ Bucket access confirmed: {self.settings.s3_bucket_name}")
        except ClientError as e:
            error_code = e.response['Error']['Code']
            if error_code == '404':
                raise S3UploadError(
                    f"S3 bucket '{self.settings.s3_bucket_name}' not found",
                    error_code="BUCKET_NOT_FOUND",
                    original_error=e
                )
            elif error_code == '403':
                raise S3UploadError(
                    f"Access denied to S3 bucket '{self.settings.s3_bucket_name}'",
                    error_code="BUCKET_ACCESS_DENIED",
                    original_error=e
                )
            else:
                raise S3UploadError(
                    f"Cannot access S3 bucket: {e}",
                    error_code="BUCKET_ACCESS_ERROR",
                    original_error=e
                )
    
    def _validate_file_size(self, image_data: bytes) -> None:
        """
        Validate file size against security limits.
        
        Args:
            image_data: The image binary data
            
        Raises:
            FileSizeError: If file is too large
        """
        file_size = len(image_data)
        
        if file_size == 0:
            raise FileSizeError("File is empty", file_size=file_size)
        
        if file_size > self.MAX_FILE_SIZE:
            raise FileSizeError(
                f"File size {file_size} bytes exceeds maximum allowed size of {self.MAX_FILE_SIZE} bytes",
                file_size=file_size,
                max_size=self.MAX_FILE_SIZE
            )
        
        logger.info(f"✅ File size validation passed: {file_size} bytes")
    
    def _detect_mime_type(self, filename: str, image_data: bytes) -> str:
        """
        Detect MIME type from filename and validate against allowed types.
        
        Args:
            filename: Original filename
            image_data: Image binary data for additional validation
            
        Returns:
            str: Detected MIME type
            
        Raises:
            S3UploadError: If MIME type is not allowed
        """
        # Try to detect from filename
        mime_type, _ = mimetypes.guess_type(filename.lower())
        
        # Fallback detection based on file signature
        if not mime_type:
            # Check PNG signature
            if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                mime_type = 'image/png'
            # Check JPEG signature
            elif image_data.startswith(b'\xff\xd8\xff'):
                mime_type = 'image/jpeg'
            # Check GIF signature
            elif image_data.startswith(b'GIF8'):
                mime_type = 'image/gif'
            # Check WebP signature
            elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
                mime_type = 'image/webp'
            else:
                mime_type = 'image/png'  # Default fallback
        
        # Validate against allowed types
        if mime_type not in self.ALLOWED_MIME_TYPES:
            raise S3UploadError(
                f"File type '{mime_type}' is not allowed. Allowed types: {', '.join(self.ALLOWED_MIME_TYPES)}",
                error_code="INVALID_MIME_TYPE"
            )
        
        logger.info(f"✅ MIME type detected: {mime_type}")
        return mime_type
    
    def _generate_unique_filename(self, original_filename: str, mime_type: str) -> str:
        """
        Generate a unique, secure filename to prevent conflicts and directory traversal.
        
        Args:
            original_filename: Original filename from user
            mime_type: Detected MIME type
            
        Returns:
            str: Unique S3 key (filename)
        """
        # Get file extension from MIME type
        extension_map = {
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png',
            'image/gif': '.gif',
            'image/webp': '.webp'
        }
        
        extension = extension_map.get(mime_type, '.png')
        
        # Generate unique identifier
        unique_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        
        # Create safe filename with folder structure
        safe_filename = f"images/{timestamp}/{unique_id}{extension}"
        
        logger.info(f"Generated unique filename: {safe_filename}")
        return safe_filename
    
    def _generate_public_url(self, s3_key: str) -> str:
        """
        Generate public URL for uploaded file.
        
        Args:
            s3_key: S3 object key
            
        Returns:
            str: Public URL for the uploaded file
        """
        public_url = f"https://{self.settings.s3_bucket_name}.s3.{self.settings.aws_region}.amazonaws.com/{s3_key}"
        return public_url
    
    async def upload_image(
        self,
        image_data: bytes,
        filename: str,
        content_type: Optional[str] = None
    ) -> UploadResult:
        """
        Upload image to S3 with security validations and public access.
        
        Args:
            image_data: Binary image data
            filename: Original filename for MIME type detection
            content_type: Optional explicit content type
            
        Returns:
            UploadResult: Upload result with public URL and metadata
            
        Raises:
            FileSizeError: If file size exceeds limits
            S3UploadError: If upload fails or validation fails
        """
        start_time = time.time()
        
        try:
            # Validate file size
            self._validate_file_size(image_data)
            
            # Detect and validate MIME type
            mime_type = content_type or self._detect_mime_type(filename, image_data)
            
            # Generate unique filename
            s3_key = self._generate_unique_filename(filename, mime_type)
            
            # Generate file hash for integrity checking
            file_hash = hashlib.md5(image_data).hexdigest()
            
            logger.info(f"🚀 Uploading image to S3: {s3_key} ({len(image_data)} bytes)")
            
            # Prepare upload parameters
            upload_params = {
                'Bucket': self.settings.s3_bucket_name,
                'Key': s3_key,
                'Body': image_data,
                'ContentType': mime_type,
                'Metadata': {
                    'original-filename': filename,
                    'upload-timestamp': datetime.now(timezone.utc).isoformat(),
                    'file-hash': file_hash
                },
                'CacheControl': 'max-age=31536000',  # 1 year cache
                'ContentDisposition': 'inline'
            }
            
            # Upload to S3 in executor to avoid blocking
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(**upload_params)
            )
            
            upload_time = time.time() - start_time
            
            # Generate public URL
            public_url = self._generate_public_url(s3_key)
            
            # Create result object
            result = UploadResult(
                public_url=public_url,
                s3_key=s3_key,
                bucket_name=self.settings.s3_bucket_name,
                file_size=len(image_data),
                mime_type=mime_type,
                upload_time=upload_time,
                etag=response.get('ETag', '').strip('"')
            )
            
            logger.info(f"✅ Upload successful in {upload_time:.2f}s: {public_url}")
            return result
            
        except FileSizeError:
            # Re-raise file size errors as-is
            raise
            
        except S3UploadError:
            # Re-raise our custom S3 errors as-is
            raise
            
        except ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            
            logger.error(f"❌ S3 ClientError {error_code}: {error_message}")
            
            if error_code == 'NoSuchBucket':
                raise S3UploadError(
                    f"S3 bucket '{self.settings.s3_bucket_name}' does not exist",
                    error_code="BUCKET_NOT_FOUND",
                    original_error=e
                )
            elif error_code == 'AccessDenied':
                raise S3UploadError(
                    "Access denied to S3 bucket. Check your permissions.",
                    error_code="ACCESS_DENIED",
                    original_error=e
                )
            else:
                raise S3UploadError(
                    f"S3 upload failed: {error_message}",
                    error_code=error_code,
                    original_error=e
                )
                
        except Exception as e:
            logger.error(f"❌ Unexpected error during upload: {e}", exc_info=True)
            raise S3UploadError(
                f"Unexpected error during upload: {str(e)}",
                error_code="UNEXPECTED_ERROR",
                original_error=e
            )
    
    async def delete_image(self, s3_key: str) -> bool:
        """
        Delete an image from S3.
        
        Args:
            s3_key: S3 object key to delete
            
        Returns:
            bool: True if deletion successful
            
        Raises:
            S3UploadError: If deletion fails
        """
        try:
            logger.info(f"🗑️  Deleting image from S3: {s3_key}")
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.delete_object(
                    Bucket=self.settings.s3_bucket_name,
                    Key=s3_key
                )
            )
            
            logger.info(f"✅ Image deleted successfully: {s3_key}")
            return True
            
        except ClientError as e:
            logger.error(f"❌ Failed to delete image {s3_key}: {e}")
            raise S3UploadError(
                f"Failed to delete image: {e}",
                error_code="DELETE_ERROR",
                original_error=e
            )
    
    def get_client_info(self) -> Dict[str, Any]:
        """
        Get information about the S3 client configuration.
        
        Returns:
            Dict[str, Any]: Client configuration information
        """
        return {
            "bucket_name": self.settings.s3_bucket_name,
            "region": self.settings.aws_region,
            "max_file_size": self.MAX_FILE_SIZE,
            "max_file_size_mb": self.MAX_FILE_SIZE / (1024 * 1024),
            "allowed_mime_types": list(self.ALLOWED_MIME_TYPES),
            "allowed_extensions": list(self.IMAGE_EXTENSIONS),
            "client_initialized": self.s3_client is not None
        }