import json
import os
import subprocess
import tempfile

from app.schemas.test_request import PerformanceTestRequest
from app.services.generators.k6_script_generator import K6ScriptGenerator
from app.services.runners.base import LoadTestRunner


class K6Runner(LoadTestRunner):

    def __init__(self):
        self.script_generator = K6ScriptGenerator()

    def run(self, request: PerformanceTestRequest) -> dict:
        script = self.script_generator.generate(request)

        script_path = None
        summary_path = None

        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".js",
                delete=False,
                encoding="utf-8"
            ) as script_file:
                script_file.write(script)
                script_path = script_file.name

            with tempfile.NamedTemporaryFile(
                suffix=".json",
                delete=False
            ) as summary_file:
                summary_path = summary_file.name

            result = subprocess.run(
                [
                    "k6",
                    "run",
                    f"--summary-export={summary_path}",
                    script_path
                ],
                capture_output=True,
                text=True,
                timeout=request.duration_seconds + 30,
                shell=False
            )

            if result.returncode != 0:
                raise RuntimeError(
                    f"k6 execution failed: {result.stderr}"
                )

            with open(summary_path, "r", encoding="utf-8") as file:
                summary = json.load(file)

            return self._parse_summary(summary)

        finally:
            if script_path and os.path.exists(script_path):
                os.remove(script_path)

            if summary_path and os.path.exists(summary_path):
                os.remove(summary_path)

    def _parse_summary(self, summary: dict) -> dict:
        metrics = summary.get("metrics", {})

        duration = metrics.get("http_req_duration", {})
        requests = metrics.get("http_reqs", {})
        failed = metrics.get("http_req_failed", {})
        checks = metrics.get("checks", {})

        total_requests = requests.get("count", 0)

        failed_requests = failed.get("passes", 0)
        successful_requests = failed.get("fails", 0)

        failure_rate = failed.get("value", 0)

        return {
            "tool": "K6",

            "totalRequests": total_requests,
            "successfulRequests": successful_requests,
            "failedRequests": failed_requests,
            "failureRate": failure_rate,

            "requestsPerSecond": requests.get("rate", 0),
            
            "avgResponseTimeMs": duration.get("avg", 0),
            "p90ResponseTimeMs": duration.get("p(90)", 0),
            "p95ResponseTimeMs": duration.get("p(95)", 0),
            "p99ResponseTimeMs": duration.get("p(99)", 0),
            "maxResponseTimeMs": duration.get("max", 0)
        }