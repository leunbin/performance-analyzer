from fastapi import APIRouter

from app.schemas.test_request import PerformanceTestRequest
from app.services.performance_test_service import PerformanceTestService

router = APIRouter(
  prefix="/api/v1/tests",
  tags=["Performance Test"]
)

service = PerformanceTestService()


@router.post("")
def run_test(request: PerformanceTestRequest):
    return service.run(request)