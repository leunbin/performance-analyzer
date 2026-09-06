from pydantic import BaseModel, Field


class ThresholdResult(BaseModel):
    name: str
    passed: bool
    actual: float | None = None
    limit: float | None = None


class StepResult(BaseModel):
    step: str
    targetRps: float
    durationSeconds: int
    expectedIterations: int

    actualRps: float
    totalRequests: int
    successfulRequests: int
    failedRequests: int
    failureRate: float

    statusCodes: dict[str, int] = Field(default_factory=dict)

    droppedIterations: int = 0

    avgResponseTimeMs: float | None = None
    p90ResponseTimeMs: float | None = None
    p95ResponseTimeMs: float | None = None
    p99ResponseTimeMs: float | None = None
    maxResponseTimeMs: float | None = None


class PerformanceTestResponse(BaseModel):
    tool: str

    # 기준을 선언했다면 그 판정 결과.
    # 선언하지 않았으면 None(판정 없음)이며,
    # False와 구분되어야 한다.
    passed: bool | None = None

    thresholds: list[ThresholdResult] = Field(
        default_factory=list
    )

    executor: str
    durationSeconds: int

    totalRequests: int
    successfulRequests: int
    failedRequests: int
    failureRate: float

    statusCodes: dict[str, int] = Field(
        default_factory=dict
    )

    requestsPerSecond: float

    # 전체 테스트에서 k6가 목표 arrival rate를
    # 유지하지 못해 시작하지 못한 iteration 수
    droppedIterations: int = 0

    # ARRIVAL_RATE 사용 시 각 부하 단계별 결과
    steps: list[StepResult] = Field(
        default_factory=list
    )

    # 도구에 따라 채우지 못하는 값이 있음 -> None
    avgResponseTimeMs: float | None = None
    p90ResponseTimeMs: float | None = None
    p95ResponseTimeMs: float | None = None
    p99ResponseTimeMs: float | None = None
    maxResponseTimeMs: float | None = None

    # Script 원본
    script: str | None = None

    # 저장된 이력 id
    runId: str | None = None