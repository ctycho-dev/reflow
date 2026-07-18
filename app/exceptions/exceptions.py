import logging
from fastapi import FastAPI, status
from fastapi.responses import JSONResponse
from app.middleware.logging import get_request_id, get_user_email


logger = logging.getLogger("app.errors")


class NotFoundError(Exception):
    """Raised when a resource is not found."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ValidationError(Exception):
    """Raised when input validation fails."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class RepositoryError(Exception):
    """Raised when an error occurs in the repository."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ConflictError(Exception):
    """Raised when an operation conflicts with current state (e.g. duplicate, full)."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class DatabaseError(Exception):
    """Exception raised for database-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ExternalServiceError(Exception):
    """Exception raised for database-related errors."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class UnauthorizedError(Exception):
    """Raised when authentication fails or is missing."""
    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


def add_exception_handlers(app: FastAPI):

    @app.exception_handler(ValueError)
    async def value_error_handler(request, exc: ValueError):
        logger.warning(
            "value_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(NotFoundError)
    async def not_found_error_handler(request, exc: NotFoundError):
        logger.info(
            "not_found_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": exc.message},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request, exc: ValidationError):
        logger.warning(
            "validation_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": exc.message},
        )
    
    @app.exception_handler(ConflictError)
    async def conflict_error_handler(request, exc: ConflictError):
        logger.info(
            "conflict_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": exc.message},
        )
    
    @app.exception_handler(UnauthorizedError)
    async def unauthorized_error_handler(request, exc: UnauthorizedError):
        logger.info(
            "unauthorized_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": exc.message},
        )

    @app.exception_handler(DatabaseError)
    async def database_error_handler(request, exc: DatabaseError):
        logger.exception(
            "database_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.message},
        )

    @app.exception_handler(RepositoryError)
    async def repository_error_handler(request, exc: RepositoryError):
        logger.exception(
            "repository_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": exc.message},
        )

    @app.exception_handler(ExternalServiceError)
    async def external_error_handler(request, exc: ExternalServiceError):
        logger.warning(
            "external_service_error",
            extra={
                "request_id": get_request_id(),
                "user_email": get_user_email() or "anonymous",
                "detail": str(exc),
                "path": request.url.path,
                "method": request.method
            },
        )
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content={"detail": exc.message},
        )
    

