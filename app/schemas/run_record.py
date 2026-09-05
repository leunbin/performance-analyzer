from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.test_request import PerformanceTestRequest
from app.schemas.test_response import PerformanceTestResponse

class RunRecord(BaseModel):
  """
  한 번 실행에 대한 조건 + 결과 + 맥락
  조건과 결과를 떼어놓으면 이 숫자가 어떤 설정이었는지 잃어버림
  항상 한 덩어리로 저장
  """

  id: str
  started_at: datetime

  #이번 실행에서 뭐가 바뀌었는지
  note: str = ""

  request: PerformanceTestRequest
  response: PerformanceTestResponse

class RunSummary(BaseModel):
  #목록에 넣을 요약

  id: str
  started_at: datetime
  note: str

  method: str
  url: str
  executor: str
  durationSeconds: int

  passed: bool | None
  requestsPerSecond: float
  p95ResponseTimeMs: float | None
  failureRate: float

class NoteUpdate(BaseModel):
  note: str = Field(max_length=500)