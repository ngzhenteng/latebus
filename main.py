from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import constants, ReplyKeyboardMarkup, Location, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
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
lta_odata_url = ""
gmap_url_base = ""
bscode_to_desc_map = {}

def get_bus_timings(bus_stop_code: str, bus_stop_desc = None) -> list:
    url = lta_odata_url + "/v3/BusArrival"

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

    bus_stop_name = bus_stop_desc if bus_stop_desc else bscode_to_desc_map[bus_stop_code]
    utc_plus_8 = timezone(timedelta(hours=8))
    curr_datetime = datetime.now(utc_plus_8)
    # print(curr_datetime)
    table = convert_svc_obj_lst_to_table(service_obj_lst, bus_stop_name, curr_datetime)
    # msg = "<b>Busses arriving at {bus_stop_name}:</b>".format(bus_stop_name=bus_stop_name) + os.linesep
    # for i in range(len(service_obj_lst)):
    #     service = service_obj_lst[i]
    #     # print(service)
    #     msg += service.get_service_info() 
    #     if i < len(service_obj_lst) - 1:
    #         msg += "\n"
    dest_encoded = bus_stop_name.replace(" ", "+")
    gmap_directn_link = "{base_url}/?api=1&destination={destination}&travelmode=walking".format(base_url=gmap_url_base, destination=dest_encoded)
    msg = "<a href='{gmap_directn_link}'>Google Maps Directions</a>\n{arr_table}".format(arr_table=table, gmap_directn_link=gmap_directn_link)
    # print(msg)
    return msg

def convert_svc_obj_lst_to_table(service_obj_lst: list[Service], bus_stop_name: str, curr_dt: datetime) -> pt.PrettyTable:
    table = pt.PrettyTable(["Bus", "Coming", "Next"])
    table.title = "<b>Arriving at {bus_stop_name}</b>".format(bus_stop_name=bus_stop_name)
    table.align['Bus'] = "c"
    table.align['Coming In'] = "c"
    table.align['Next'] = "c"
    # table.align['Following'] = "l"
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
    for bus_stop in bus_stop_arr:
        bscode = bus_stop["BusStopCode"]
        desc = bus_stop["Description"]
        bscode_to_desc_map[bscode] = desc

def get_bus_stops(skip: int) -> list[dict]:
    url = lta_odata_url + "/BusStops"

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
    # print(arg_list)
    if not arg_list: 
        await update.message.reply_text("please provide 1 bus stop code", parse_mode=constants.ParseMode.HTML)
    else:
        bust_stop_code = arg_list[0]
        reply_markup = InlineKeyboardMarkup([InlineKeyboardButton("Update")])
        print(reply_markup)
        await update.message.reply_text(get_bus_timings(bust_stop_code), reply_markup = reply_markup, parse_mode=constants.ParseMode.MARKDOWN_V2, link_preview_options=LinkPreviewOptions(is_disabled=True))
    
# todo: store favourites here
async def start(update, context):
    await update.message.reply_text(
        "<b>How to use</b>:\n\n"
        "`1. /start` - Start the bot\n"
        "`2. /busstop 43029` - Get all bus timings at bus stop 43029\n"
        "`3. Send your location via the telegram buttons and click on your desired bus stop\n",
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
    if command == '/busstop' or command == '/updatebusstop':
        bus_stop_code = query_data_split[1]
        first_whitespace_idx = query_data.index(" ")
        second_whitespace_idx = query_data.index(" ", first_whitespace_idx + 1)
        bus_stop_desc = query_data[second_whitespace_idx + 1:]
        callback_data_str = "/updatebusstop {bus_stop_code} {bus_stop_desc}".format(bus_stop_code=bus_stop_code, bus_stop_desc=bus_stop_desc)
        reply_markup = InlineKeyboardMarkup([[InlineKeyboardButton("Update", callback_data=callback_data_str)]])
        if command == '/busstop': 
            await update.callback_query.message.reply_text(get_bus_timings(bus_stop_code, bus_stop_desc), reply_markup = reply_markup,  parse_mode=constants.ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
        else:
            await update.callback_query.message.edit_text(get_bus_timings(bus_stop_code, bus_stop_desc), reply_markup=reply_markup, parse_mode=constants.ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
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
    lta_odata_url = os.getenv("LTA_ODATA_URL")
    gmap_url_base = os.getenv("GMAP_URL_BASE")
    getAllBusStops()
    main()


