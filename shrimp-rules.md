# Image API Development Guidelines

## Project Overview

- **Purpose**: RESTful API for image processing, manipulation, and management
- **Core Functions**: Upload, download, resize, format conversion, metadata extraction
- **Security Focus**: File validation, size limits, type restrictions

## Project Architecture

### Directory Structure Standards

- **Create** `/src` as main source directory
- **Create** `/src/routes` for API endpoint definitions
- **Create** `/src/middleware` for authentication, validation, error handling
- **Create** `/src/services` for image processing logic
- **Create** `/src/models` for data schemas and database interactions
- **Create** `/src/utils` for helper functions and utilities
- **Create** `/src/config` for environment and configuration files
- **Create** `/tests` for unit and integration tests
- **Create** `/uploads` for temporary file storage (add to .gitignore)
- **Create** `/docs` for API documentation

### File Organization Rules

- Place all route handlers in `/src/routes`
- Place business logic in `/src/services`
- Keep middleware functions in `/src/middleware`
- Store utility functions in `/src/utils`

## Code Standards

### Naming Conventions

- **Files**: Use kebab-case (e.g., `image-processor.js`, `auth-middleware.js`)
- **Functions**: Use camelCase (e.g., `processImage`, `validateFileType`)
- **Constants**: Use UPPER_SNAKE_CASE (e.g., `MAX_FILE_SIZE`, `ALLOWED_FORMATS`)
- **API Endpoints**: Use kebab-case (e.g., `/api/images/resize`, `/api/images/metadata`)

### Required File Headers

- **Always include** JSDoc comments for all exported functions
- **Always specify** parameter types and return types
- **Always document** error conditions and exceptions

## API Endpoint Standards

### Endpoint Design Rules

- **Use** RESTful conventions: GET, POST, PUT, DELETE
- **Prefix** all endpoints with `/api/v1`
- **Structure** image endpoints as `/api/v1/images/{action}`
- **Use** plural nouns for resource collections
- **Return** consistent JSON response format

### Required Endpoints

- `POST /api/v1/images/upload` - Upload new image
- `GET /api/v1/images/:id` - Retrieve image by ID
- `DELETE /api/v1/images/:id` - Delete image by ID
- `POST /api/v1/images/:id/resize` - Resize existing image
- `POST /api/v1/images/:id/convert` - Convert image format
- `GET /api/v1/images/:id/metadata` - Get image metadata

### Response Format Standards

```json
{
  "success": boolean,
  "data": object|array|null,
  "message": string,
  "error": object|null
}
```

## Security Requirements

### File Upload Security

- **Validate** file extensions against whitelist: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`
- **Check** MIME types, do not rely on file extensions alone
- **Limit** file size to maximum 10MB per upload
- **Scan** uploaded files for malicious content
- **Generate** unique filenames to prevent conflicts and directory traversal
- **Store** uploaded files outside web root directory

### Authentication & Authorization

- **Implement** JWT-based authentication for all non-public endpoints
- **Add** rate limiting middleware to prevent abuse
- **Validate** all input parameters and sanitize user data
- **Use** HTTPS only in production environment

## Image Processing Standards

### Supported Operations

- **Resize**: Maintain aspect ratio by default, allow custom dimensions
- **Format Conversion**: Support JPEG, PNG, WebP output formats
- **Quality Control**: Allow quality settings for JPEG (1-100)
- **Metadata Extraction**: EXIF data, dimensions, file size, creation date

### Processing Rules

- **Always** preserve original image unless explicitly requested to overwrite
- **Generate** thumbnails automatically for images larger than 1MB
- **Apply** lossless compression when possible
- **Log** all processing operations for audit trail

## Error Handling Standards

### Error Response Format

```json
{
  "success": false,
  "data": null,
  "message": "User-friendly error message",
  "error": {
    "code": "ERROR_CODE",
    "details": "Technical error details"
  }
}
```

### Required Error Codes

- `INVALID_FILE_TYPE` - Unsupported file format
- `FILE_TOO_LARGE` - Exceeds size limit
- `PROCESSING_FAILED` - Image processing error
- `UNAUTHORIZED` - Authentication required
- `NOT_FOUND` - Image not found
- `RATE_LIMIT_EXCEEDED` - Too many requests

## Framework and Dependencies

### Required Dependencies

- **Express.js** for web framework
- **Multer** for file upload handling
- **Sharp** for image processing operations
- **JWT** for authentication tokens
- **Helmet** for security headers
- **Cors** for cross-origin requests

### Prohibited Dependencies

- **Do not use** ImageMagick due to security vulnerabilities
- **Avoid** synchronous file operations in request handlers
- **Do not use** eval() or similar dynamic code execution

## Testing Requirements

### Test Coverage Rules

- **Write** unit tests for all service functions
- **Create** integration tests for all API endpoints
- **Test** file upload scenarios with various file types
- **Validate** error handling for all failure cases
- **Test** authentication and authorization flows

### Test File Naming

- Unit tests: `*.test.js` in same directory as source
- Integration tests: `/tests/integration/*.test.js`
- Test data: `/tests/fixtures/`

## Database and Storage

### File Storage Rules

- **Use** cloud storage (AWS S3, Google Cloud) for production
- **Implement** local file system storage for development
- **Store** file metadata in database, not file contents
- **Create** database schema for image records with fields: id, filename, originalName, size, mimeType, uploadedAt, userId

### Database Schema Requirements

```sql
CREATE TABLE images (
  id UUID PRIMARY KEY,
  filename VARCHAR(255) NOT NULL,
  original_name VARCHAR(255) NOT NULL,
  size INTEGER NOT NULL,
  mime_type VARCHAR(100) NOT NULL,
  uploaded_at TIMESTAMP DEFAULT NOW(),
  user_id UUID REFERENCES users(id)
);
```

## Configuration Management

### Environment Variables

- **Define** `NODE_ENV` for environment detection
- **Set** `MAX_FILE_SIZE` for upload limits
- **Configure** `UPLOAD_DIR` for file storage path
- **Specify** `JWT_SECRET` for token signing
- **Set** `DATABASE_URL` for database connection

### Configuration File Structure

- **Create** `/src/config/index.js` for centralized configuration
- **Load** environment-specific settings
- **Validate** required environment variables on startup

## Documentation Requirements

### API Documentation

- **Generate** OpenAPI/Swagger documentation
- **Document** all endpoints with request/response examples
- **Include** authentication requirements
- **Provide** error code explanations

### Code Documentation

- **Write** README.md with setup instructions
- **Document** deployment procedures
- **Include** troubleshooting guide
- **Maintain** changelog for API versions

## Performance Standards

### Optimization Rules

- **Implement** image compression for uploads
- **Use** streaming for large file operations
- **Cache** processed images for repeated requests
- **Monitor** memory usage during image processing
- **Set** appropriate timeouts for processing operations

## Deployment Standards

### Production Checklist

- **Enable** HTTPS with valid SSL certificates
- **Configure** proper CORS policies
- **Set** security headers with Helmet.js
- **Implement** logging with structured format
- **Monitor** application performance and errors
- **Backup** database and file storage regularly

## Prohibited Actions

- **Never** store sensitive data in plain text
- **Never** execute user-provided code
- **Never** allow direct file system access via API
- **Never** commit environment variables or secrets
- **Never** use deprecated or vulnerable dependencies
- **Never** process files without size validation
- **Never** trust client-provided MIME types exclusively