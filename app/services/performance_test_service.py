from fastapi import HTTPException

from app.schemas.test_request import (
    LoadTestTool,
    PerformanceTestRequest,
)
from app.services.runners.k6_runner import K6Runner


class PerformanceTestService:

    def __init__(self):
        self.runners = {
            LoadTestTool.K6: K6Runner()
        }

    def run(self, request: PerformanceTestRequest) -> dict:
        runner = self.runners.get(request.tool)

        if runner is None:
            raise HTTPException(
                status_code=400,
                detail=f"{request.tool.value} is not supported yet"
            )

        return runner.run(request)