from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class APIErrorDetail(BaseModel):
    code: str
    message: str
    request_id: Optional[str] = None
    details: Optional[dict] = None


class APIErrorResponse(BaseModel):
    error: APIErrorDetail


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    page: int
    page_size: int
    total: int
    total_pages: int


class StandardResponse(BaseModel, Generic[T]):
    data: T
    meta: Optional[dict] = None


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_env: str
    database: str
    redis: str
    mock_mode: bool
