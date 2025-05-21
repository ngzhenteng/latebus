from dataclasses import dataclass
from model.service import Service

@dataclass
class BusArrival:
    odata_metadata: str
    BusStopCode: str
    Services: list[Service]

    # def __init__(self, **kwargs):
    #     for k, v in kwargs.items():
    #         if k == "odata.metadata":
    #             continue
    #         setattr(self, k, v)