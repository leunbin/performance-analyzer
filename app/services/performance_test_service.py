import subprocess

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

    def available_tools(self) -> list[dict]:
        return[
            {"tool": tool.value, "available": tool in self.runners}
            for tool in LoadTestTool
        ]

    def run(self, request: PerformanceTestRequest) -> dict:
        runner = self.runners.get(request.tool)

        if runner is None:
            raise HTTPException(
                status_code=400,
                detail=f"{request.tool.value} is not supported yet"
            )

        try:
            return runner.run(request)
        except subprocess.TimoutExpired:
            raise HTTPException(
                status_code=504,
                detail="The load generator did not finish in time."
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=503,
                detail=f"{request.tool.value} is not installed on this server."
            )
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error))