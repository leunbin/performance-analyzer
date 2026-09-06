from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

class LoadTestTool(str, Enum):
  K6 = "K6"
  JMETER = "JMETER"

class HttpMethod(str, Enum):
  GET = "GET"
  POST = "POST"
  PUT = "PUT"
  PATCH = "PATCH"
  DELETE = "DELETE"
  HEAD = "HEAD"

class Executor(str, Enum):
  """
  부하 모델
  CONSTANT_VUS / RAMPING_VUS는 closed model.
  VU가 응답을 받아야 다음 요청을 보내므로 서버가 느려지면 부하도 같이 줄어듦.
  한계를 찾으려면 도착률을 고정하는 open model(ARRIVAL_RATE)를 써야함.
  """

  CONSTANT_VUS = "CONSTANT_VUS"
  RAMPING_VUS = "RAMPING_VUS"
  ARRIVAL_RATE = "ARRIVAL_RATE"

class Stage(BaseModel):
  """
  target의 의미는 executor에 따라 달라짐.

  CONSTANT_VUS / RAMPING_VUS -> 동사 VU 수
  ARRIVAL_RATE -> 초당 요청 수
  """

  target: int = Field(ge=0, le=2000)
  duration_seconds: int = Field(ge=1, le=1800)

class Thresholds(BaseModel):
  """
  실행 전에 선언하는 합격 기준
  하나라도 위반하면 테스트는 실패
  """

  p95_ms: int | None = Field(default=None, ge=1)
  p99_ms: int | None = Field(default=None, ge=1)
  max_failure_rate: float | None = Field(default=None, ge=0, le=1)

  def is_empty(self) -> bool:
    return(
      self.p95_ms is None
      and self.p99_ms is None
      and self.max_failure_rate is None
    )

class BodyRandomization(BaseModel):
  path: list[str | int] = Field(min_length=1)
  values: list[Any] = Field(min_length=1)

class PerformanceTestRequest(BaseModel):
  tool: LoadTestTool

  method: HttpMethod
  url: str
  headers: dict[str, str] = {}
  body: dict[str, Any] | None = None
  body_randomization: BodyRandomization | None = None

  executor: Executor = Executor.CONSTANT_VUS
  stages: list[Stage] = Field(min_length=1, max_length=10)

  #Closed Model에서 sleep이 없으면 동시 사용자가 아니라 vu로 낼 수 있는 최대 처리량으로 재게
  #둘은 다른 테스트
  think_time_seconds: float = Field(default=0.0, ge=0, le=60)

  #ARRIVAL_RATE 에서 도착률을 감당한 VU 풀 크기. 부족하면 K6가 경고
  pre_allocated_vus: int | None= Field(default=None, ge=1, le=2000)

  thresholds: Thresholds = Thresholds()

  # 상태 코드 집계는 k6 raw JSON 출력을 파싱한다. 장시간 soak 에서는
  # 파일이 수 GB 까지 커지므로 그때는 꺼야 한다.
  collect_status_codes: bool = True

  @property
  def total_duration_seconds(self) -> int:
    return sum(stage.duration_seconds for stage in self.stages)

  @model_validator(mode="after")
  def check(self) -> "PerformanceTestRequest":
        if not self.url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")

        if self.body_randomization is not None and self.body is None:
            raise ValueError("body_randomization requires a request body")

        if self.total_duration_seconds > 3600:
            raise ValueError("total duration must not exceed 3600 seconds")

        if self.executor == Executor.CONSTANT_VUS and len(self.stages) != 1:
            raise ValueError("CONSTANT_VUS takes exactly one stage")

        if self.method in (HttpMethod.GET, HttpMethod.HEAD) and self.body is not None:
            raise ValueError(f"{self.method.value} requests must not carry a body")

        if self.executor == Executor.CONSTANT_VUS and self.stages[0].target < 1:
            raise ValueError("CONSTANT_VUS requires target of at least 1")

        if self.executor == Executor.ARRIVAL_RATE and self.pre_allocated_vus is None:
            # 도착률의 2배를 기본값으로. 응답이 느리면 VU 가 물려서 모자란다.
            self.pre_allocated_vus = min(
                2000, max(stage.target for stage in self.stages) * 2 or 1
            )

        return self