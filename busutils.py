import requests
from model.next_bus import NextBusObj
from model.service import Service
import heapq
import haversine
from haversine import Unit
import prettytable as pt
from datetime import datetime, timezone, timedelta

from langchain_core.vectorstores import InMemoryVectorStore
from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings

class BusUtils:
    bus_stop_arr = [] # list of json objs representing bus stops
    lta_odata_url = ""
    gmap_url_base = ""
    lta_acc_key = ""
    bscode_to_desc_map = {}
    bsdesc_to_code_map = {}
    busstop_vector_store = None

    # TODO: only allow 1 initialization of all these member variables
    def __init__(self, lta_odata_url, lta_acc_key, gmap_url_base):
        self.lta_odata_url = lta_odata_url
        self.lta_acc_key = lta_acc_key
        self.gmap_url_base = gmap_url_base
        self.populate_all_bus_stops()
    
    def get_bus_stops(self, skip: int) -> list[dict]:
        url = self.lta_odata_url + "/BusStops"

        # payload = {}
        params = {
            '$skip': skip
        }
        headers = {
            'AccountKey': self.lta_acc_key,
            'accept': 'application/json'
        }
        response = requests.request("GET", url, headers=headers, params=params)
        if response.status_code != 200: 
            print("datamall resp status code: " + str(response.status_code))
        response_json = response.json()
        return response_json["value"]
    
    def get_bus_timings_via_bus_stop_desc(self, bus_stop_desc: str) -> str:
        bus_stop_code = self.bsdesc_to_code_map[bus_stop_desc]
        if bus_stop_code:
            return self.get_bus_timings(bus_stop_code)
        return "Bus stop name {bus_stop_desc} not recognised".format(bus_stop_desc=bus_stop_desc)

    def get_bus_timings(self, bus_stop_code: str) -> str:
        def service_obj_sorter(service_obj: Service):
            service_no = service_obj.ServiceNo;
            service_no_digit_str = "".join([char for char in service_no if char.isdigit()])
            return int(service_no_digit_str)
            
        url = self.lta_odata_url + "/v3/BusArrival"
        if not self.bscode_to_desc_map[bus_stop_code]: raise Exception(f"bus_stop_code {bus_stop_code} does not exist")

        # payload = {}
        params = {
            'BusStopCode': bus_stop_code
        }
        headers = {
            'AccountKey': self.lta_acc_key,
            'accept': 'application/json'
        }
        response = requests.request("GET", url, headers=headers, params=params)
        if response.status_code != 200: 
            print("datamall /v3/BusArrival resp status code: " + str(response.status_code))
            return
        response_json = response.json()
        service_obj_lst = []
        for service in response_json["Services"]:
            # print(service)
            next_bus = NextBusObj(**service["NextBus"]) if "NextBus" in service else None
            next_bus2 = NextBusObj(**service["NextBus2"]) if "NextBus2" in service else None
            next_bus3 = NextBusObj(**service["NextBus3"]) if "NextBus3" in service else None
            service_obj = Service(
                ServiceNo=service["ServiceNo"],
                Operator=service["Operator"],
                NextBus=next_bus,
                NextBus2=next_bus2,
                NextBus3=next_bus3
            )
            service_obj_lst.append(service_obj)

        service_obj_lst.sort(key=service_obj_sorter)
        bus_stop_name = self.bscode_to_desc_map[bus_stop_code]
        utc_plus_8 = timezone(timedelta(hours=8))
        curr_datetime = datetime.now(utc_plus_8)
        # print(curr_datetime)
        table = self.convert_svc_obj_lst_to_table(service_obj_lst, bus_stop_name, curr_datetime)
        # msg = "<b>Busses arriving at {bus_stop_name}:</b>".format(bus_stop_name=bus_stop_name) + os.linesep
        # for i in range(len(service_obj_lst)):
        #     service = service_obj_lst[i]
        #     # print(service)
        #     msg += service.get_service_info() 
        #     if i < len(service_obj_lst) - 1:
        #         msg += "\n"
        dest_encoded = bus_stop_name.replace(" ", "+")
        gmap_directn_link = "{base_url}/?api=1&destination={destination}&travelmode=walking".format(base_url=self.gmap_url_base, destination=dest_encoded)
        msg = "[Navigate using google maps]({gmap_directn_link})\n{arr_table}".format(arr_table=table, gmap_directn_link=gmap_directn_link)
        # print(msg)
        return msg

    def convert_svc_obj_lst_to_table(self, service_obj_lst: list[Service], bus_stop_name: str, curr_dt: datetime) -> pt.PrettyTable:
        table = pt.PrettyTable(["Bus", "Coming", "Next"])
        table.title = "__Arriving at {bus_stop_name}__".format(bus_stop_name=bus_stop_name)
        table.align['Bus'] = "c"
        table.align['Coming In'] = "c"
        table.align['Next'] = "c"
        # table.align['Following'] = "l"
        for service in service_obj_lst:
            table.add_row(service.get_service_info_as_lst(curr_dt))
        return table

    def get_nearest_bus_stops(self, i: int, user_coords: tuple) -> list[dict]:
        bus_stops_heap = []
        for bus_stop in self.bus_stop_arr:
            bus_stop_coords = (bus_stop["Latitude"], bus_stop["Longitude"])
            dist = haversine.haversine(user_coords, bus_stop_coords, unit=Unit.METERS)
            heapq.heappush(bus_stops_heap, (dist, bus_stop))
        return heapq.nsmallest(i, bus_stops_heap)

    def get_bus_stop_arr(self, limit: int = None) -> list[dict]:
        if limit:
            return self.bus_stop_arr[:limit]
        return self.bus_stop_arr
    
    # def get_busstop_desc_to_code_map(self):
    #     return self.bsdesc_to_code_map

    def search_busstop(self, description: str) -> list:
        results = self.busstop_vector_store.similarity_search(query=description, k=5)
        return results

    def populate_all_bus_stops(self):
        skip_records = 0
        bus_stops = self.get_bus_stops(skip_records)
        while bus_stops:
            self.bus_stop_arr.extend(bus_stops)
            skip_records += 500
            bus_stops = self.get_bus_stops(skip_records)
        vector_store_documents = []

        for i in range(0, len(self.bus_stop_arr)):
            bus_stop = self.bus_stop_arr[i]
            bus_stop_code = bus_stop["BusStopCode"]
            desc = bus_stop["Description"]
            road_name = bus_stop["RoadName"]
            self.bscode_to_desc_map[bus_stop_code] = desc
            self.bsdesc_to_code_map[desc] = bus_stop_code
            vector_store_documents.append(Document(id=i, page_content=desc, metadata={"bus_stop_code": bus_stop_code, "road_name": road_name}))

        # vector store
        embeddings = GoogleGenerativeAIEmbeddings(model="models/embedding-001")
        self.busstop_vector_store = InMemoryVectorStore(embeddings)
        self.busstop_vector_store.add_documents(vector_store_documents) # TODO: allow all bus stops to be embedded in vectorstore, not just 10.





