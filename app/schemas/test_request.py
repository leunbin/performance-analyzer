from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

class LoadTestTool(str, Enum):
  K6 = "K6"
  JMETER = "JMETER"

class PerformanceTestRequest(BaseModel):
  tool: LoadTestTool = LoadTestTool.K6

  method: str
  url: str
  headers: dict[str, str] = {}
  body: dict[str, Any] | None = None

  vus: int = Field(default=10, ge=1, le=500)
  duration_seconds: int = Field(default=10, ge=1, le=300)