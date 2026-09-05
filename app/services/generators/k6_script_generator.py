import json

from app.schemas.test_request import PerformanceTestRequest


class K6ScriptGenerator:

    def generate(self, request: PerformanceTestRequest) -> str:
        method = request.method.upper()

        url_json = json.dumps(str(request.url))
        headers_json = json.dumps(request.headers)

        if request.body is not None:
            body_json = json.dumps(request.body)
            body_script = f"JSON.stringify({body_json})"
        else:
            body_script = "null"

        script = f"""
import http from 'k6/http';
import {{ check }} from 'k6';

export const options = {{
    vus: {request.vus},
    duration: "{request.duration_seconds}s",

    summaryTrendStats: [
        'avg',
        'min',
        'med',
        'max',
        'p(90)',
        'p(95)',
        'p(99)'
    ],
}};

export default function () {{
    const url = {url_json};

    const headers = {headers_json};

    const params = {{
        headers: headers,
    }};

    const body = {body_script};

    http.request(
        "{method}",
        url,
        body,
        params
    );

    check(response, {{
        'status is 2xx': (r) => r.status >= 200 && r.status < 300,
    }});
}}
"""

        return script