from fastapi import APIRouter

from app.schemas.test_request import PerformanceTestRequest
from app.schemas.test_response import PerformanceTestResponse
from app.services.performance_test_service import PerformanceTestService

router = APIRouter(
  prefix="/api/v1/tests",
  tags=["Performance Test"]
)

service = PerformanceTestService()


@router.post("", response_model=PerformanceTestResponse)
def run_test(request: PerformanceTestRequest) -> PerformanceTestResponse:
    return service.run(request)