"""Common Pydantic schemas shared across the API."""

from typing import Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error details in unified error response."""

    code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error message")
    details: object | None = Field(None, description="Additional error details")


class ErrorResponse(BaseModel):
    """Unified error response returned by all endpoints."""

    error: ErrorDetail


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    page: int = Field(1, ge=1, description="Page number (1-based)")
    size: int = Field(20, ge=1, le=100, description="Page size (max 100)")

    @property
    def offset(self) -> int:
        """Calculate SQL OFFSET from page and size."""
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    """Paginated response wrapper."""

    items: list[T]
    total: int = Field(..., description="Total number of items")
    page: int = Field(..., description="Current page number")
    size: int = Field(..., description="Page size")
    pages: int = Field(..., description="Total number of pages")

    @classmethod
    def create(cls, items: list[T], total: int, page: int, size: int) -> "Page[T]":
        """Build a Page from items, total count, page and size."""
        pages = (total + size - 1) // size if size > 0 else 0
        return cls(items=items, total=total, page=page, size=size, pages=pages)
