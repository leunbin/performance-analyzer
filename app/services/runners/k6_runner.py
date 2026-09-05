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
        raw_output_path = None

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

            with tempfile.NamedTemporaryFile(
                suffix=".json",
                delete=False
            ) as raw_output_file:
                raw_output_path = raw_output_file.name

            result = subprocess.run(
                [
                    "k6",
                    "run",
                    f"--summary-export={summary_path}",
                    "--out",
                    f"json={raw_output_path}",
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

            status_codes = self._parse_status_codes(raw_output_path)

            return self._parse_summary(
                summary,
                status_codes
            )

        finally:
            if script_path and os.path.exists(script_path):
                os.remove(script_path)

            if summary_path and os.path.exists(summary_path):
                os.remove(summary_path)

            if raw_output_path and os.path.exists(raw_output_path):
                os.remove(raw_output_path)

    def _parse_summary(
        self,
        summary: dict,
        status_codes: dict[str, int]
    ) -> dict:
        metrics = summary.get("metrics", {})

        duration = metrics.get("http_req_duration", {})
        requests = metrics.get("http_reqs", {})
        failed = metrics.get("http_req_failed", {})

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
            "statusCodes": status_codes,
            "requestsPerSecond": requests.get("rate", 0),
            "avgResponseTimeMs": duration.get("avg", 0),
            "p90ResponseTimeMs": duration.get("p(90)", 0),
            "p95ResponseTimeMs": duration.get("p(95)", 0),
            "p99ResponseTimeMs": duration.get("p(99)", 0),
            "maxResponseTimeMs": duration.get("max", 0)
        }

    def _parse_status_codes(
        self,
        raw_output_path: str
    ) -> dict[str, int]:
        status_codes: dict[str, int] = {}

        with open(
            raw_output_path,
            "r",
            encoding="utf-8"
        ) as file:
            for line in file:
                if not line.strip():
                    continue

                event = json.loads(line)

                if event.get("type") != "Point":
                    continue

                if event.get("metric") != "http_req_duration":
                    continue

                data = event.get("data", {})
                tags = data.get("tags", {})

                status = tags.get("status")

                if status is None:
                    continue

                status_codes[status] = (
                    status_codes.get(status, 0) + 1
                )

        return status_codes