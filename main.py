from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import constants, ReplyKeyboardMarkup, Location, InlineKeyboardButton, InlineKeyboardMarkup
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta
import os
import requests
from model.next_bus import NextBusObj
from model.service import Service
import heapq
import haversine
from haversine import Unit
import prettytable as pt

bus_stop_arr = [] # list of json objs representing bus stops

def get_bus_timings(bus_stop_code: str, bus_stop_desc = None) -> list:
    url = os.getenv("LTA_BUSARR_URL")

    lta_acc_key = os.getenv("LTA_ACC_KEY")
    # payload = {}
    params = {
        'BusStopCode': bus_stop_code
    }
    headers = {
        'AccountKey': lta_acc_key,
        'accept': 'application/json'
    }
    response = requests.request("GET", url, headers=headers, params=params)
    response_json = response.json()
    service_obj_lst = []
    for service in response_json["Services"]:
        print(service)
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

    bus_stop_name = bus_stop_desc if bus_stop_desc else bus_stop_code
    utc_plus_8 = timezone(timedelta(hours=8))
    curr_datetime = datetime.now(utc_plus_8)
    print(curr_datetime)
    table = convert_svc_obj_lst_to_table(service_obj_lst, bus_stop_name, curr_datetime)
    # msg = "<b>Busses arriving at {bus_stop_name}:</b>".format(bus_stop_name=bus_stop_name) + os.linesep
    # for i in range(len(service_obj_lst)):
    #     service = service_obj_lst[i]
    #     # print(service)
    #     msg += service.get_service_info() 
    #     if i < len(service_obj_lst) - 1:
    #         msg += "\n"
    msg = "<pre>{arr_table}</pre>".format(arr_table=table)
    print(msg)
    return msg

def convert_svc_obj_lst_to_table(service_obj_lst: list[Service], bus_stop_name: str, curr_dt: datetime) -> pt.PrettyTable:
    table = pt.PrettyTable(["Bus", "Coming", "Next", "Following"])
    table.title = "<b>Busses arriving at {bus_stop_name}</b>".format(bus_stop_name=bus_stop_name)
    table.align['Bus'] = "l"
    table.align['Coming In'] = "l"
    table.align['Next'] = "l"
    table.align['Following'] = "l"
    for service in service_obj_lst:
        table.add_row(service.get_service_info_as_lst(curr_dt))
    return table

def get_nearest_bus_stops(i: int, user_coords: tuple) -> list[dict]:
    bus_stops_heap = []
    for bus_stop in bus_stop_arr:
        bus_stop_coords = (bus_stop["Latitude"], bus_stop["Longitude"])
        dist = haversine.haversine(user_coords, bus_stop_coords, unit=Unit.METERS)
        heapq.heappush(bus_stops_heap, (dist, bus_stop))
    return heapq.nsmallest(i, bus_stops_heap)


def getAllBusStops():
    skip_records = 0
    bus_stops = get_bus_stops(skip_records)
    while bus_stops:
        bus_stop_arr.extend(bus_stops)
        skip_records += 500
        bus_stops = get_bus_stops(skip_records)
    # print(len(bus_stop_arr))
    # print(bus_stop_arr[:5])


def get_bus_stops(skip: int) -> list[dict]:
    url = "https://datamall2.mytransport.sg/ltaodataservice/BusStops"

    lta_acc_key = os.getenv("LTA_ACC_KEY")
    # payload = {}
    params = {
        '$skip': skip
    }
    headers = {
        'AccountKey': lta_acc_key,
        'accept': 'application/json'
    }
    response = requests.request("GET", url, headers=headers, params=params)
    if response.status_code != 200: 
        print("datamall resp status code: " + str(response.status_code))
    response_json = response.json()
    return response_json["value"]



async def bus_timings_handler(update, context):
    arg_list = context.args
    print(arg_list)
    if not arg_list: 
        await update.message.reply_text("please provide 1 bus stop code", parse_mode=constants.ParseMode.HTML)
    else:
        bust_stop_code = arg_list[0]
        await update.message.reply_text(get_bus_timings(bust_stop_code),  parse_mode=constants.ParseMode.HTML)
    
# todo: store favourites here
async def start(update, context):
    await update.message.reply_text(
        "<b>Basic Commands</b>:\n\n"
        "`/start` - Start the bot\n"
        "`/busstop 43029` - Get all bus timings at bus stop 43029\n"
        "`Send your location via the telegram buttons and click on your desired bus stop for timings\n",
        parse_mode=constants.ParseMode.HTML
    )

async def nearby_bus_stops_handler(update, context):
    location = update.message.location
    user_coords = (location.latitude, location.longitude)
    nearest_bus_stops = get_nearest_bus_stops(5, user_coords)
    def convert_bus_stop_to_button(bus_stop: dict, dist_to_bus_stop: float):
        bus_stop_desc = bus_stop["Description"]
        message = "{description} - {distance}m".format(description=bus_stop_desc, distance=int(dist_to_bus_stop))
        callback_data_str = "/busstop {bus_stop_code} {bus_stop_desc}".format(bus_stop_code=bus_stop["BusStopCode"], bus_stop_desc=bus_stop_desc)
        return InlineKeyboardButton(message, callback_data=callback_data_str)
    keyboard = []
    for nearest_bus_stop in nearest_bus_stops:
        distance = nearest_bus_stop[0]
        bus_stop = nearest_bus_stop[1]
        keyboard.append([convert_bus_stop_to_button(bus_stop, distance)])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Nearest bus stops:", reply_markup=reply_markup)

async def callbackHandler(update, context):
    query = update.callback_query
    query_data = query.data
    query_data_split = query_data.split()
    command = query_data_split[0]
    if command == '/busstop':
        bus_stop_code = query_data_split[1]
        first_whitespace_idx = query_data.index(" ")
        second_whitespace_idx = query_data.index(" ", first_whitespace_idx + 1)
        # third_whitespace_idx = query_data.index(" ", second_whitespace_idx + 1)
        bus_stop_desc = query_data[second_whitespace_idx + 1:]
        
        # bust_stop_code = arg_list[0]
        await update.callback_query.message.reply_text(get_bus_timings(bus_stop_code, bus_stop_desc),  parse_mode=constants.ParseMode.HTML)
    else:
        # CallbackQueries need to be answered, even if no notification to the user is needed
        # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
        await query.answer()


def main():
    token = os.getenv("TELE_BOT_API_KEY")
    application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    application.add_handler(CommandHandler("busstop", bus_timings_handler))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, nearby_bus_stops_handler))
    application.add_handler(CallbackQueryHandler(callbackHandler))
    print("Telegram Bot started!", flush=True)
    application.run_polling()

if __name__ == "__main__":
    load_dotenv()
    getAllBusStops()
    # get_bus_timings("43029")
    main()


