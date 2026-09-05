import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.schemas.run_record import RunRecord, RunSummary
from app.schemas.test_request import PerformanceTestRequest
from app.schemas.test_response import PerformanceTestResponse

# 레포 안이 아니라 홈 아래에 쌓는다. 측정 이력은 코드가 아니고,
# 레포를 다시 클론해도 살아남아야 한다.
DEFAULT_DIR = Path(
    os.getenv("ANALYZER_HISTORY_DIR", Path.home() / ".performance-analyzer" / "runs")
)


class HistoryService:

    def __init__(self, directory: Path = DEFAULT_DIR):
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        request: PerformanceTestRequest,
        response: PerformanceTestResponse,
        started_at: datetime,
        note: str = "",
    ) -> RunRecord:
        # 파일명이 곧 정렬 키가 되도록 시각을 앞에 둔다.
        stamp = started_at.strftime("%Y%m%dT%H%M%S")
        record = RunRecord(
            id=f"{stamp}-{uuid.uuid4().hex[:6]}",
            started_at=started_at,
            note=note,
            request=request,
            response=response,
        )
        self._path(record.id).write_text(
            record.model_dump_json(indent=2), encoding="utf-8"
        )
        return record

    def list(self, limit: int = 50) -> list[RunSummary]:
        summaries = []

        for path in sorted(self.directory.glob("*.json"), reverse=True)[:limit]:
            record = self._read(path)
            if record is None:
                continue

            summaries.append(RunSummary(
                id=record.id,
                started_at=record.started_at,
                note=record.note,
                method=record.request.method.value,
                url=record.request.url,
                executor=record.response.executor,
                durationSeconds=record.response.durationSeconds,
                passed=record.response.passed,
                requestsPerSecond=record.response.requestsPerSecond,
                p95ResponseTimeMs=record.response.p95ResponseTimeMs,
                failureRate=record.response.failureRate,
            ))

        return summaries

    def get(self, run_id: str) -> RunRecord | None:
        return self._read(self._path(run_id))

    def set_note(self, run_id: str, note: str) -> RunRecord | None:
        record = self.get(run_id)
        if record is None:
            return None

        record.note = note
        self._path(run_id).write_text(
            record.model_dump_json(indent=2), encoding="utf-8"
        )
        return record

    def delete(self, run_id: str) -> bool:
        path = self._path(run_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def _path(self, run_id: str) -> Path:
        # run_id 가 경로로 새어나가지 않게 파일명만 취한다.
        return self.directory / f"{Path(run_id).name}.json"

    def _read(self, path: Path) -> RunRecord | None:
        try:
            return RunRecord.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:
            # 스키마가 바뀌기 전에 저장된 파일은 건너뛴다.
            # 하나가 깨졌다고 목록 전체가 죽으면 안 된다.
            return None


def now() -> datetime:
    return datetime.now(timezone.utc)