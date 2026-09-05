from fastapi import FastAPI

from app.api.test_router import router as test_router

app = FastAPI(
  title = "Performance Analyzer",
  version = "0.1.0"
)

app.include_router(test_router)

@app.get("/health")
def health_check():
  return {"status": "ok"}