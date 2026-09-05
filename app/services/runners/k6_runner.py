from app.schemas.test_request import PerformanceTestRequest
from app.services.runners.base import LoadTestRunner

class K6Runner(LoadTestRunner):

  def run(self, request: PerformanceTestRequest) -> dict:
    return{
      "tool": "K6",
      "status": "READY",
      "method": request.method,
      "url" : request.url,
      "vus": request.vus,
      "durationSeconds": request.duration_seconds
    }