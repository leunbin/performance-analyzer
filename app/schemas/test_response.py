from pydantic import BaseModel, Field

class ThresholdResult(BaseModel):
  name: str
  passed: bool
  actual: float | None = None
  limit: float | None = None

class PerformanceTestResponse(BaseModel):
  tool: str

   # 기준을 선언했다면 그 판정 결과. 선언하지 않았으면 None(판정 없음)이며,
  # False 와 구분되어야 한다.
  passed: bool | None = None
  thresholds: list[ThresholdResult] = Field(default_factory=list)

  executor: str
  durationSeconds: int
  
  totalRequests: int
  successfulRequests: int
  failedRequests: int
  failureRate: float

  statusCodes: dict[str, int] = Field(default_factory=dict)

  requestsPerSecond: float

  #도구를 따라 못 채우는 값이 있음 -> None으로 보냄
  avgResponseTimeMs: float | None = None
  p90ResponseTimeMs: float | None = None
  p95ResponseTimeMs: float | None = None
  p99ResponseTimeMs: float | None = None
  maxResponseTimeMs: float | None = None

  #Script 원본
  script: str | None = None

  #저장된 이력 id
  runId: str | None = None