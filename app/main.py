import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.test_router import router as test_router

app = FastAPI(
  title = "Performance Analyzer",
  version = "0.1.0"
)

origins = [
  origin.strip()
  for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
  if origin.strip()
]

if origins:
  app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
  )

app.include_router(test_router)

@app.get("/health")
def health_check():
  return {"status": "ok"}

static_dir = Path(__file__).parent / "static"
if static_dir.is_dir():
  app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")