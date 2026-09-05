from typing import Any

from pydantic import BaseModel, Field

class PerformanceTestRequest(BaseModel):
  method: str
  url: str
  headers: dict[str, str] = {}
  body: dict[str, Any] | None = None

  vus: int = Field(default=10, ge=1, le=500)
  duration_seconds: int = Field(default=10, ge=1, le=300)