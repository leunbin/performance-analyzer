import json

from app.schemas.test_request import (
    Executor,
    PerformanceTestRequest,
    Thresholds,
)


class K6ScriptGenerator:

    def generate(self, request: PerformanceTestRequest) -> str:
        options = {
            "scenarios": {"default": self._scenario(request)},
            "summaryTrendStats": [
                "avg", "min", "med", "max", "p(90)", "p(95)", "p(99)"
            ],
        }

        thresholds = self._thresholds(request.thresholds)
        if thresholds:
            options["thresholds"] = thresholds

        sleep_line = (
            f"    sleep({request.think_time_seconds});"
            if request.think_time_seconds > 0
            else "    // think time 없음: 최대 처리량을 측정하는 설정이다"
        )

        body_script = (
            f"JSON.stringify({json.dumps(request.body)})"
            if request.body is not None
            else "null"
        )

        return f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {json.dumps(options, indent=2)};

export default function () {{
    const response = http.request(
        {json.dumps(request.method.value)},
        {json.dumps(request.url)},
        {body_script},
        {{ headers: {json.dumps(request.headers)} }}
    );

    check(response, {{
        'status is 2xx': (r) => r.status >= 200 && r.status < 300,
    }});

{sleep_line}
}}

export function handleSummary(data) {{
    return {{ [__ENV.SUMMARY_PATH]: JSON.stringify(data) }};
}}
"""

    def _scenario(self, request: PerformanceTestRequest) -> dict:
        stages = [
            {"target": s.target, "duration": f"{s.duration_seconds}s"}
            for s in request.stages
        ]

        if request.executor == Executor.CONSTANT_VUS:
            return {
                "executor": "constant-vus",
                "vus": request.stages[0].target,
                "duration": f"{request.stages[0].duration_seconds}s",
            }

        if request.executor == Executor.RAMPING_VUS:
            return {
                "executor": "ramping-vus",
                "startVUs": 0,
                "stages": stages,
            }

        # ARRIVAL_RATE: 도착률을 고정하는 open model.
        # 서버가 느려져도 부하가 줄지 않으므로 한계 지점이 드러난다.
        return {
            "executor": "ramping-arrival-rate",
            "startRate": 0,
            "timeUnit": "1s",
            "preAllocatedVUs": request.pre_allocated_vus,
            "stages": stages,
        }

    def _thresholds(self, thresholds: Thresholds) -> dict:
        result: dict[str, list[str]] = {}

        duration = []
        if thresholds.p95_ms is not None:
            duration.append(f"p(95)<{thresholds.p95_ms}")
        if thresholds.p99_ms is not None:
            duration.append(f"p(99)<{thresholds.p99_ms}")
        if duration:
            result["http_req_duration"] = duration

        if thresholds.max_failure_rate is not None:
            result["http_req_failed"] = [
                f"rate<{thresholds.max_failure_rate}"
            ]

        return result