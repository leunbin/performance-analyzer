import json

from app.schemas.test_request import (
    Executor,
    PerformanceTestRequest,
    Thresholds,
)


class K6ScriptGenerator:

    def generate(self, request: PerformanceTestRequest) -> str:
        body_setup = ""
        body_script = "null"

        if request.body is not None:
            if request.body_randomization is None:
                body_script = f"JSON.stringify({json.dumps(request.body)})"
            else:
                body_setup = self._randomized_body_script(request)
                body_script = "JSON.stringify(body)"

        options = {
            "scenarios": self._scenarios(request),
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

        return f"""import http from 'k6/http';
import {{ check, sleep }} from 'k6';

export const options = {json.dumps(options, indent=2)};

export default function () {{
{body_setup}

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

    def _scenarios(self, request: PerformanceTestRequest) -> dict:
        stages = [
            {"target": s.target, "duration": f"{s.duration_seconds}s"}
            for s in request.stages
        ]

        if request.executor == Executor.CONSTANT_VUS:
            return {
                "default": {
                    "executor": "constant-vus",
                    "vus": request.stages[0].target,
                    "duration": f"{request.stages[0].duration_seconds}s",
                }
            }

        if request.executor == Executor.RAMPING_VUS:
            return {
                "default": {
                    "executor": "ramping-vus",
                    "startVUs": 0,
                    "stages": stages,
                }
            }

        # ARRIVAL_RATE:
        # 각 stage의 목표 RPS를 일정 시간 유지하는 계단식 open model.
        scenarios = {}
        start_seconds = 0

        for index, stage in enumerate(request.stages, start=1):
            scenarios[f"step_{index}"] = {
                "executor": "constant-arrival-rate",
                "rate": stage.target,
                "timeUnit": "1s",
                "duration": f"{stage.duration_seconds}s",
                "startTime": f"{start_seconds}s",
                "preAllocatedVUs": request.pre_allocated_vus,
                "tags": {
                    "step": f"step_{index}",
                    "target_rps": str(stage.target),
                },
            }

            start_seconds += stage.duration_seconds

        return scenarios

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

    def _randomized_body_script( self, request: PerformanceTestRequest,) -> str:
        randomization = request.body_randomization

        path = "".join(
            f"[{part}]" if isinstance(part, int)
            else f"[{json.dumps(part)}]"
            for part in randomization.path
        )

        return f"""    
            const body = {json.dumps(request.body)};
            const randomValues = {json.dumps(randomization.values)};
            body{path} = randomValues[Math.floor(Math.random() * randomValues.length)];
            """