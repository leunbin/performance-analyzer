# Performance analyzer

k6를 래핑해 부하테스트 조건과 결과를 한 덩어리로 기록하는 로컬 도구.

부하테스트를 반복하다 보면 "이 숫자가 어떤 설정이었지"를 계속 잃어버린다.
조건, 결과, 그리고 이번에 무엇을 바꿨는지를 항상 같이 저장하는 것이 목적이다.

## 실행

k6가 설치돼 있어야 한다.

```bash
pip install -r requirements.txt
uvicorn app.main:app --port 9000
```

http://localhost:9000 을 열면 UI가 뜬다. API 문서는 /docs.

프론트는 빌드가 필요 없는 단일 HTML 파일(`app/static/index.html`)이다.

## 이력

실행 결과는 `~/.performance-analyzer/runs/` 에 JSON으로 쌓인다.
`ANALYZER_HISTORY_DIR` 로 위치를 바꿀 수 있다.

## 개념

- **executor** — `CONSTANT_VUS` / `RAMPING_VUS` 는 closed model 이라 서버가 느려지면
  부하도 같이 줄어든다. 한계를 찾으려면 도착률을 고정하는 `ARRIVAL_RATE` 를 쓴다.
- **think_time_seconds** — 0이면 "동시 사용자 N명"이 아니라 "최대 처리량"을 재는 것이다.
- **thresholds** — 실행 전에 선언한 합격 기준. k6는 위반 시 exit 99로 끝나며,
  이는 실행 실패가 아니라 `passed: false` 로 변환된다.

## API

| Method | Path | |
|---|---|---|
| GET | `/api/v1/tools` | 설치된 부하 생성기 |
| POST | `/api/v1/tests` | 실행. 결과는 자동 저장 |
| GET | `/api/v1/runs` | 이력 목록 |
| GET | `/api/v1/runs/{id}` | 조건 + 결과 전체 |
| PATCH | `/api/v1/runs/{id}` | 변경 메모 수정 |
| DELETE | `/api/v1/runs/{id}` | 삭제 |