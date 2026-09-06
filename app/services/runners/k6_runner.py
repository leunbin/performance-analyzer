import json
import math
import os
import re
import subprocess
import tempfile
from collections import defaultdict

from app.schemas.test_request import Executor, PerformanceTestRequest
from app.services.generators.k6_script_generator import K6ScriptGenerator
from app.services.runners.base import LoadTestRunner


# k6 는 threshold 위반 시 99 로 종료한다.
# 테스트 자체는 정상 수행된 것이므로 실패로 취급하면 안 된다.
# 이걸 에러로 던지면 가장 중요한 결과를 잃는다.
THRESHOLD_BREACHED = 99

# JVM 부팅이나 결과 집계 같은 도구별 오버헤드.
# 러너가 각자 정한다.
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

            # status code 수집뿐 아니라 ARRIVAL_RATE의
            # step별 metric / dropped iterations 분석에도
            # raw output이 필요하다.
            needs_raw_output = (
                request.collect_status_codes
                or request.executor == Executor.ARRIVAL_RATE
            )

            if needs_raw_output:
                paths["raw"] = self._temp(".json")
                command += [
                    "--out",
                    f"json={paths['raw']}",
                ]

            command.append(paths["script"])

            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=(
                    request.total_duration_seconds
                    + STARTUP_OVERHEAD_SECONDS
                ),
                shell=False,
                env={
                    **os.environ,
                    "SUMMARY_PATH": paths["summary"],
                },
            )

            if result.returncode not in (
                0,
                THRESHOLD_BREACHED,
            ):
                raise RuntimeError(
                    f"k6 execution failed: {result.stderr}"
                )

            with open(
                paths["summary"],
                "r",
                encoding="utf-8",
            ) as file:
                summary = json.load(file)

            status_codes = (
                self._parse_status_codes(paths["raw"])
                if request.collect_status_codes
                else {}
            )

            parsed = self._parse_summary(
                summary,
                status_codes,
            )

            # 전체 dropped_iterations도 summary에서 가져온다.
            parsed["droppedIterations"] = (
                self._parse_total_dropped_iterations(summary)
            )

            # ARRIVAL_RATE에서는 각 부하 단계의 결과를
            # 별도로 집계한다.
            if request.executor == Executor.ARRIVAL_RATE:
                parsed["steps"] = self._parse_step_metrics(
                    raw_output_path=paths["raw"],
                    request=request,
                )
            else:
                parsed["steps"] = []

            parsed["executor"] = request.executor.value
            parsed["durationSeconds"] = (
                request.total_duration_seconds
            )
            parsed["script"] = script

            if request.thresholds.is_empty():
                parsed["passed"] = None
                parsed["thresholds"] = []
            else:
                parsed["passed"] = (
                    result.returncode
                    != THRESHOLD_BREACHED
                )

            return parsed

        finally:
            for path in paths.values():
                if path and os.path.exists(path):
                    os.remove(path)

    def _temp(
        self,
        suffix: str,
        content: str | None = None,
    ) -> str:
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=suffix,
            delete=False,
            encoding="utf-8",
        ) as file:
            if content is not None:
                file.write(content)

            return file.name

    def _parse_summary(
        self,
        summary: dict,
        status_codes: dict,
    ) -> dict:
        metrics = summary.get("metrics", {})

        duration = (
            metrics
            .get("http_req_duration", {})
            .get("values", {})
        )

        requests = (
            metrics
            .get("http_reqs", {})
            .get("values", {})
        )

        failed = (
            metrics
            .get("http_req_failed", {})
            .get("values", {})
        )

        # http_req_failed 는 "실패 여부" Rate 다.
        # passes 가 실패 건수이고 fails 가 성공 건수다.
        failed_requests = failed.get("passes", 0)
        successful_requests = failed.get("fails", 0)

        return {
            "tool": "K6",
            "thresholds": self._parse_thresholds(
                metrics,
                duration,
                failed,
            ),
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

    def _parse_step_metrics(
        self,
        raw_output_path: str,
        request: PerformanceTestRequest,
    ) -> list[dict]:
        steps = defaultdict(
            lambda: {
                "durations": [],
                "totalRequests": 0,
                "successfulRequests": 0,
                "failedRequests": 0,
                "statusCodes": {},
                "droppedIterations": 0,
            }
        )

        with open(
            raw_output_path,
            "r",
            encoding="utf-8",
        ) as file:
            for line in file:
                if not line.strip():
                    continue

                event = json.loads(line)

                if event.get("type") != "Point":
                    continue

                metric = event.get("metric")
                data = event.get("data", {})
                tags = data.get("tags", {})
                step = tags.get("step")

                # step tag가 없는 metric은
                # 구간별 집계 대상에서 제외한다.
                if step is None:
                    continue

                # HTTP 요청 하나당 http_req_duration Point 하나를
                # 기준으로 요청 수와 응답시간을 집계한다.
                if metric == "http_req_duration":
                    value = data.get("value")

                    if value is None:
                        continue

                    step_data = steps[step]

                    step_data["durations"].append(
                        float(value)
                    )
                    step_data["totalRequests"] += 1

                    status = tags.get("status")

                    if status is not None:
                        status = str(status)

                        step_data["statusCodes"][status] = (
                            step_data["statusCodes"].get(
                                status,
                                0,
                            )
                            + 1
                        )

                    if (
                        status is not None
                        and status.startswith("2")
                    ):
                        step_data[
                            "successfulRequests"
                        ] += 1
                    else:
                        step_data[
                            "failedRequests"
                        ] += 1

                # k6가 목표 arrival rate를 유지하지 못한 경우
                # dropped_iterations metric이 발생한다.
                elif metric == "dropped_iterations":
                    value = data.get("value")

                    if value is None:
                        continue

                    steps[step]["droppedIterations"] += int(
                        float(value)
                    )

        result: list[dict] = []

        for index, stage in enumerate(
            request.stages,
            start=1,
        ):
            step_name = f"step_{index}"
            data = steps[step_name]

            durations = data["durations"]
            total_requests = data["totalRequests"]
            failed_requests = data["failedRequests"]

            target_rps = stage.target
            duration_seconds = stage.duration_seconds

            actual_rps = (
                total_requests / duration_seconds
                if duration_seconds > 0
                else 0.0
            )

            expected_iterations = (
                target_rps * duration_seconds
            )

            result.append({
                "step": step_name,
                "targetRps": target_rps,
                "durationSeconds": duration_seconds,
                "expectedIterations": (
                    expected_iterations
                ),
                "actualRps": actual_rps,
                "totalRequests": total_requests,
                "successfulRequests": data[
                    "successfulRequests"
                ],
                "failedRequests": failed_requests,
                "failureRate": (
                    failed_requests / total_requests
                    if total_requests > 0
                    else 0.0
                ),
                "statusCodes": data["statusCodes"],
                "droppedIterations": data[
                    "droppedIterations"
                ],
                "avgResponseTimeMs": (
                    sum(durations) / len(durations)
                    if durations
                    else None
                ),
                "p90ResponseTimeMs": self._percentile(
                    durations,
                    0.90,
                ),
                "p95ResponseTimeMs": self._percentile(
                    durations,
                    0.95,
                ),
                "p99ResponseTimeMs": self._percentile(
                    durations,
                    0.99,
                ),
                "maxResponseTimeMs": (
                    max(durations)
                    if durations
                    else None
                ),
            })

        return result

    def _parse_total_dropped_iterations(
        self,
        summary: dict,
    ) -> int:
        metrics = summary.get("metrics", {})

        dropped = (
            metrics
            .get("dropped_iterations", {})
            .get("values", {})
        )

        return int(dropped.get("count", 0))

    def _percentile(
        self,
        values: list[float],
        percentile: float,
    ) -> float | None:
        if not values:
            return None

        sorted_values = sorted(values)

        index = (
            len(sorted_values) - 1
        ) * percentile

        lower = math.floor(index)
        upper = math.ceil(index)

        if lower == upper:
            return sorted_values[lower]

        weight = index - lower

        return (
            sorted_values[lower] * (1 - weight)
            + sorted_values[upper] * weight
        )

    def _parse_thresholds(
        self,
        metrics: dict,
        duration: dict,
        failed: dict,
    ) -> list[dict]:
        results = []

        for metric_name, metric in metrics.items():
            for expression, outcome in (
                metric.get("thresholds") or {}
            ).items():

                # k6 버전에 따라 {"ok": bool}
                # 또는 {"fails": int} 로 온다.
                if "ok" in outcome:
                    passed = bool(outcome["ok"])
                else:
                    passed = (
                        outcome.get("fails", 0) == 0
                    )

                actual = None
                limit = None

                match = THRESHOLD_PATTERN.match(
                    expression
                )

                if match:
                    stat = match.group(1)
                    raw_limit = match.group(2)

                    limit = float(raw_limit)

                    source = (
                        duration
                        if metric_name
                        == "http_req_duration"
                        else failed
                    )

                    actual = source.get(stat)

                results.append({
                    "name": (
                        f"{metric_name}: {expression}"
                    ),
                    "passed": passed,
                    "actual": actual,
                    "limit": limit,
                })

        return results

    def _parse_status_codes(
        self,
        raw_output_path: str,
    ) -> dict[str, int]:
        status_codes: dict[str, int] = {}

        with open(
            raw_output_path,
            "r",
            encoding="utf-8",
        ) as file:
            for line in file:
                if not line.strip():
                    continue

                event = json.loads(line)

                if event.get("type") != "Point":
                    continue

                if (
                    event.get("metric")
                    != "http_req_duration"
                ):
                    continue

                status = (
                    event
                    .get("data", {})
                    .get("tags", {})
                    .get("status")
                )

                if status is None:
                    continue

                status = str(status)

                status_codes[status] = (
                    status_codes.get(status, 0) + 1
                )

        return status_codes