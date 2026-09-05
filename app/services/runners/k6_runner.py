import json
import os
import re
import subprocess
import tempfile

from app.schemas.test_request import PerformanceTestRequest
from app.services.generators.k6_script_generator import K6ScriptGenerator
from app.services.runners.base import LoadTestRunner

# k6 는 threshold 위반 시 99 로 종료한다. 테스트 자체는 정상 수행된 것이므로
# 실패로 취급하면 안 된다. 이걸 에러로 던지면 가장 중요한 결과를 잃는다.
THRESHOLD_BREACHED = 99

# JVM 부팅이나 결과 집계 같은 도구별 오버헤드. 러너가 각자 정한다.
STARTUP_OVERHEAD_SECONDS = 30

THRESHOLD_PATTERN = re.compile(r"^(.+?)\s*<\s*([0-9.]+)$")


class K6Runner(LoadTestRunner):

    def __init__(self):
        self.script_generator = K6ScriptGenerator()

    def run(self, request: PerformanceTestRequest) -> dict:
        script = self.script_generator.generate(request)

        paths: dict[str, str] = {}

        try:
            paths["script"] = self._temp(".js", script)
            paths["summary"] = self._temp(".json")

            command = ["k6", "run", "--quiet"]

            if request.collect_status_codes:
                paths["raw"] = self._temp(".json")
                command += ["--out", f"json={paths['raw']}"]

            command.append(paths["script"])

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=request.total_duration_seconds + STARTUP_OVERHEAD_SECONDS,
                shell=False,
                env={**os.environ, "SUMMARY_PATH": paths["summary"]},
            )

            if result.returncode not in (0, THRESHOLD_BREACHED):
                raise RuntimeError(f"k6 execution failed: {result.stderr}")

            with open(paths["summary"], "r", encoding="utf-8") as file:
                summary = json.load(file)

            status_codes = (
                self._parse_status_codes(paths["raw"])
                if request.collect_status_codes
                else {}
            )

            parsed = self._parse_summary(summary, status_codes)
            parsed["executor"] = request.executor.value
            parsed["durationSeconds"] = request.total_duration_seconds
            parsed["script"] = script

            if request.thresholds.is_empty():
                parsed["passed"] = None
                parsed["thresholds"] = []
            else:
                parsed["passed"] = result.returncode != THRESHOLD_BREACHED

            return parsed

        finally:
            for path in paths.values():
                if path and os.path.exists(path):
                    os.remove(path)

    def _temp(self, suffix: str, content: str | None = None) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=suffix, delete=False, encoding="utf-8"
        ) as file:
            if content is not None:
                file.write(content)
            return file.name

    def _parse_summary(self, summary: dict, status_codes: dict) -> dict:
        metrics = summary.get("metrics", {})

        duration = metrics.get("http_req_duration", {}).get("values", {})
        requests = metrics.get("http_reqs", {}).get("values", {})
        failed = metrics.get("http_req_failed", {}).get("values", {})

        # http_req_failed 는 "실패 여부" Rate 다. passes 가 실패 건수이고
        # fails 가 성공 건수다. 헷갈리기 쉬우니 이름을 바꿔 받는다.
        failed_requests = failed.get("passes", 0)
        successful_requests = failed.get("fails", 0)

        return {
            "tool": "K6",
            "thresholds": self._parse_thresholds(metrics, duration, failed),
            "totalRequests": requests.get("count", 0),
            "successfulRequests": successful_requests,
            "failedRequests": failed_requests,
            "failureRate": failed.get("rate", 0.0),
            "statusCodes": status_codes,
            "requestsPerSecond": requests.get("rate", 0.0),
            "avgResponseTimeMs": duration.get("avg"),
            "p90ResponseTimeMs": duration.get("p(90)"),
            "p95ResponseTimeMs": duration.get("p(95)"),
            "p99ResponseTimeMs": duration.get("p(99)"),
            "maxResponseTimeMs": duration.get("max"),
        }

    def _parse_thresholds(
        self, metrics: dict, duration: dict, failed: dict
    ) -> list[dict]:
        results = []

        for metric_name, metric in metrics.items():
            for expression, outcome in (metric.get("thresholds") or {}).items():
                # k6 버전에 따라 {"ok": bool} 또는 {"fails": int} 로 온다.
                if "ok" in outcome:
                    passed = bool(outcome["ok"])
                else:
                    passed = outcome.get("fails", 0) == 0

                actual = None
                limit = None

                match = THRESHOLD_PATTERN.match(expression)
                if match:
                    stat, raw_limit = match.group(1), match.group(2)
                    limit = float(raw_limit)
                    source = duration if metric_name == "http_req_duration" else failed
                    actual = source.get(stat)

                results.append({
                    "name": f"{metric_name}: {expression}",
                    "passed": passed,
                    "actual": actual,
                    "limit": limit,
                })

        return results

    def _parse_status_codes(self, raw_output_path: str) -> dict[str, int]:
        status_codes: dict[str, int] = {}

        with open(raw_output_path, "r", encoding="utf-8") as file:
            for line in file:
                if not line.strip():
                    continue

                event = json.loads(line)

                if event.get("type") != "Point":
                    continue
                if event.get("metric") != "http_req_duration":
                    continue

                status = event.get("data", {}).get("tags", {}).get("status")
                if status is None:
                    continue

                status_codes[status] = status_codes.get(status, 0) + 1

        return status_codes