from abc import ABC, abstractmethod

from app.schemas.test_request import PerformanceTestRequest

class LoadTestRunner(ABC):

  @abstractmethod
  def run(self, request: PerformanceTestRequest) -> dict:
    pass