"""Shared exceptions used across the application."""

from fastapi import HTTPException, status


class NotFoundError(HTTPException):
    def __init__(self, resource: str, resource_id: str = ""):
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} '{resource_id}' not found"
        super().__init__(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Access denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class ConflictError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class InvalidTransitionError(HTTPException):
    def __init__(self, current_status: str, event: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Cannot apply event '{event}' to case in status '{current_status}'",
        )


class ValidationError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail
        )
