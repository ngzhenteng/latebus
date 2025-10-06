from model.service import Service
from abc import ABC, abstractmethod

class ServiceSortStrategy(ABC):
    @abstractmethod
    def service_obj_sorter(self, service_obj: Service) -> int:
        pass