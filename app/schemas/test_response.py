from pydantic import BaseModel, Field

class PerformanceTestResponse(BaseModel):
  tool: str

  totalRequests: int
  successfulRequests: int
  failedRequests: int
  failureRate: float

  statusCodes: dict[str, int] = Field(default_factory=dict)

  requestsPerSecond: float

  avgResponseTimeMs: float
  p90ResponseTimeMs: float
  p95ResponseTimeMs: float
  p99ResponseTimeMs: float
  maxResponseTimeMs: float