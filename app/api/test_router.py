from fastapi import APIRouter, HTTPException

from app.schemas.run_record import NoteUpdate, RunRecord, RunSummary
from app.schemas.test_request import PerformanceTestRequest
from app.schemas.test_response import PerformanceTestResponse
from app.services.history_service import HistoryService, now
from app.services.performance_test_service import PerformanceTestService

router = APIRouter(
  prefix="/api/v1",
  tags=["Performance Test"]
)

service = PerformanceTestService()
history = HistoryService()

@router.get("/tools")
def list_tools() -> list[dict]:
    return service.available_tools()

@router.post("/tests", response_model=PerformanceTestResponse)
def run_test(request: PerformanceTestRequest) -> PerformanceTestResponse:
    started_at = now()
    result = service.run(request)

    # 실행은 성공했는데 저장이 실패했다고 결과를 버릴 수는 없다.
    try:
        record = history.save(
            request,
            PerformanceTestResponse.model_validate(result),
            started_at,
        )
        result["runId"] = record.id
    except OSError:
        result["runId"] = None

    return result

@router.get("/runs", response_model=list[RunSummary])
def list_runs(limit: int = 50) -> list[RunSummary]:
    return history.list(limit=limit)


@router.get("/runs/{run_id}", response_model=RunRecord)
def get_run(run_id: str) -> RunRecord:
    record = history.get(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No run with that id.")
    return record

@router.patch("/runs/{run_id}", response_model=RunRecord)
def update_note(run_id: str, update: NoteUpdate) -> RunRecord:
    record = history.set_note(run_id, update.note)
    if record is None:
        raise HTTPException(status_code=404, detail="No run with that id.")
    return record

@router.delete("/runs/{run_id}", status_code=204)
def delete_run(run_id: str) -> None:
    if not history.delete(run_id):
        raise HTTPException(status_code=404, detail="No run with that id.")