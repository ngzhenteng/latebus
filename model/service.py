from dataclasses import dataclass
from model.next_bus import NextBusObj
from datetime import datetime

@dataclass
class Service:
    ServiceNo: str
    Operator: str
    NextBus: NextBusObj
    NextBus2: NextBusObj
    NextBus3: NextBusObj

    # TODO: Figure out why NextBusObj is still a dict, and not the class. But somehow the class hierarchy is recognised....


    def get_service_info_as_lst(self, curr_dt: datetime) -> str:
        service_info_lst = []
        next_bus = self.NextBus.getTimeToArr(curr_dt) if self.NextBus else "NA"
        next_bus_2 = self.NextBus2.getTimeToArr(curr_dt) if self.NextBus2 else "NA"
        next_bus_3 = self.NextBus3.getTimeToArr(curr_dt) if self.NextBus3 else "NA"
        service_info_lst.append(self.ServiceNo)
        service_info_lst.append(next_bus)
        service_info_lst.append(next_bus_2)
        service_info_lst.append(next_bus_3)
        return service_info_lst

    def get_service_info(self) -> str:
        service_info = "{service_no} | {next_bus} | {next_bus_2} | {next_bus_3}"
        next_bus = self.NextBus.getArrTime() if self.NextBus else "NA"
        next_bus_2 = self.NextBus2.getArrTime() if self.NextBus2 else "NA"
        next_bus_3 = self.NextBus3.getArrTime() if self.NextBus3 else "NA"
        return service_info.format(service_no=self.ServiceNo, next_bus=next_bus, next_bus_2=next_bus_2, next_bus_3=next_bus_3)
        



