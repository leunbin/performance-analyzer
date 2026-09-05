from fastapi import APIRouter

from app.schemas.test_request import PerformanceTestRequest

router = APIRouter(
  prefix="/api/v1/tests",
  tags=["Performance Test"]
)

@router.post("")
def run_test(request: PerformanceTestRequest):
  return{
    "message": "Performance test request received",
    "request": request
  }