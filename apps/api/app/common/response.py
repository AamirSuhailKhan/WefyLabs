from typing import Generic, TypeVar, Optional, Any, Dict
from pydantic import BaseModel, Field

T = TypeVar("T")

class APIErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Any] = None

class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    meta: Optional[Dict[str, Any]] = Field(default_factory=dict)
    requestId: str = ""

class APIErrorResponse(BaseModel):
    success: bool = False
    error: APIErrorDetail
    requestId: str = ""

def create_success_response(data: Any = None, meta: Optional[Dict[str, Any]] = None, request_id: str = "") -> APIResponse:
    return APIResponse(
        success=True,
        data=data,
        meta=meta or {},
        requestId=request_id
    )

def create_error_response(code: str, message: str, details: Optional[Any] = None, request_id: str = "") -> APIErrorResponse:
    return APIErrorResponse(
        success=False,
        error=APIErrorDetail(code=code, message=message, details=details),
        requestId=request_id
    )
