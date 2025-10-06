from model.service import Service
from sort_strategy.service_sort_strategy_abc import ServiceSortStrategy

from datetime import timezone, timedelta, datetime

class ServiceNoSortStrategy(ServiceSortStrategy):
    def service_obj_sorter(self, service_obj: Service) -> int:
        service_no = service_obj.ServiceNo if service_obj else None
        if service_no is None:
            return (100000, 100000)
        service_no_digit_str = "".join([char for char in service_no if char.isdigit()])
        next_bus = service_obj.NextBus if service_obj else None
        utc_plus_8 = timezone(timedelta(hours=8))
        curr_datetime = datetime.now(utc_plus_8)
        try:
            nextBusSecsToArr = next_bus.getTimeToArrInSecs(curr_datetime) if next_bus else 100000
            return (int(service_no_digit_str), int(nextBusSecsToArr))
        except:
            return (100000, 100000)


