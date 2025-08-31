from dataclasses import dataclass
from datetime import datetime

@dataclass
class NextBusObj:
    OriginCode: str
    DestinationCode: str
    EstimatedArrival: str
    Monitored: int
    Latitude: str
    Longitude: str
    VisitNumber: str
    Load: str
    Feature: str
    Type: str

    # returns the arrival time of this NextBusObj in hh:MM format e.g. 11:24
    def getArrTime(self) -> str:
        if not self.EstimatedArrival or len(self.EstimatedArrival) == 0: return "NA"
        arr_datetime = datetime.strptime(self.EstimatedArrival, "%Y-%m-%dT%H:%M:%S%z")
        hour = arr_datetime.hour
        minute = arr_datetime.minute
        return "{hour:02}:{minute:02}".format(hour=hour, minute=minute)
    
    # returns the time to this NextBusObj in MM:ss format e.g. 04m3s
    def getTimeToArr(self, curr_datetime: datetime) -> str:
        try:
            diff_in_secs = self.getTimeToArrInSecs(curr_datetime)
            if (diff_in_secs <= 0.0): return "Arr"
            minutes, seconds = divmod(int(diff_in_secs), 60)
            return "{minutes}m {seconds}s".format(minutes=minutes, seconds=seconds)
        except:
            return "NA"


    def getTimeToArrInSecs(self, curr_datetime: datetime) -> float:
        if not self.EstimatedArrival or len(self.EstimatedArrival) == 0: raise ValueError("EstimatedArrival is NA")
        if self.EstimatedArrival == "Arr": return 0.0
        arr_datetime = datetime.strptime(self.EstimatedArrival, "%Y-%m-%dT%H:%M:%S%z")
        diff_in_secs = (arr_datetime - curr_datetime).total_seconds()
        return diff_in_secs

