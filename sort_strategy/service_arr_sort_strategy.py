from model.service import Service
from sort_strategy.service_sort_strategy_abc import ServiceSortStrategy

from datetime import timezone, timedelta, datetime

class ServiceArrSortStrategy(ServiceSortStrategy):
    def service_obj_sorter(self, service_obj: Service) -> tuple[int, int]:
        next_bus = service_obj.NextBus if service_obj else None
        following_bus = service_obj.NextBus2 if service_obj else None
        utc_plus_8 = timezone(timedelta(hours=8))
        curr_datetime = datetime.now(utc_plus_8)
        try:
            nextBusSecsToArr = next_bus.getTimeToArrInSecs(curr_datetime) if next_bus else 100000
            folBusSecsToArr = following_bus.getTimeToArrInSecs(curr_datetime) if following_bus else 100000
            return (int(nextBusSecsToArr), int(folBusSecsToArr))
        except:
            return (100000, 100000)
