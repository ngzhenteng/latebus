from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler
from telegram import constants, ReplyKeyboardMarkup, Location, InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, KeyboardButton
from dotenv import load_dotenv
import os
import traceback

from busutils import BusUtils
from aiagent import AiAgent
from model.tele_bus_arr_msg import TeleBusArrMsg
from sort_strategy.service_sort_strategy_abc import ServiceSortStrategy
from sort_strategy.service_no_sort_strategy import ServiceNoSortStrategy
from sort_strategy.service_arr_sort_strategy import ServiceArrSortStrategy

bus_utils = None
ai_agent = None

async def bus_timings_handler(update, context):
    arg_list = context.args
    # print(arg_list)
    if not arg_list: 
        await update.message.reply_text("please provide 1 bus stop code", parse_mode=constants.ParseMode.MARKDOWN)
    else:
        bust_stop_code = arg_list[0]
        reply_markup = InlineKeyboardMarkup([InlineKeyboardButton("Update")])
        await update.message.reply_text(bus_utils.get_bus_timings(bust_stop_code, ServiceNoSortStrategy()), reply_markup = reply_markup, parse_mode=constants.ParseMode.MARKDOWN, link_preview_options=LinkPreviewOptions(is_disabled=True))
    
# todo: store favourites here
async def start(update, context):
    reply_markup = get_bus_stop_near_me_keyboard_markup()
    await update.message.reply_text(
       "<b>Welcome to latebus, your Bus Arrival Time AI Agent</b>\n\n"
        "- ❔ Simply chat! You can ask any questions, e.g. <i>“bus arrivals at Toa Payoh Stn”</i>.\n"
        "- 📍 Or send your location via the Telegram button, then tap your desired bus stop from the list.\n",
        parse_mode=constants.ParseMode.HTML, reply_markup=reply_markup)

def get_bus_stop_near_me_keyboard_markup():
    location_keyboard = KeyboardButton(text="Bus Stops Near Me", request_location=True)
    custom_keyboard = [[location_keyboard]]
    reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True)
    return reply_markup

async def nearby_bus_stops_handler(update, context):
    location = update.message.location
    user_coords = (location.latitude, location.longitude)
    nearest_bus_stops = bus_utils.get_nearest_bus_stops(5, user_coords)
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

def get_tele_bus_arr_msg(main_msg: str, bus_stop_code: str, bus_stop_desc: str = None) -> TeleBusArrMsg:
    reply_markup = None
    if bus_stop_code:
        if bus_stop_desc:
            updatebusstop_callback_str = "/updatebusstop {bus_stop_code} {bus_stop_desc}".format(bus_stop_code=bus_stop_code, bus_stop_desc=bus_stop_desc)
            updatebusstopSortByArr_callback_str = "/updatebusstopSortByArr {bus_stop_code} {bus_stop_desc}".format(bus_stop_code=bus_stop_code, bus_stop_desc=bus_stop_desc)
        else:
            updatebusstop_callback_str = "/updatebusstop {bus_stop_code}".format(bus_stop_code=bus_stop_code)
            updatebusstopSortByArr_callback_str = "/updatebusstopSortByArr {bus_stop_code}".format(bus_stop_code=bus_stop_code)
        reply_markup = InlineKeyboardMarkup([[
            InlineKeyboardButton("🔄(sort by bus no.)", callback_data=updatebusstop_callback_str),
            InlineKeyboardButton("🔄(sort by arriv.)", callback_data=updatebusstopSortByArr_callback_str),
        ]])
    return TeleBusArrMsg(main_msg, reply_markup)


async def callbackHandler(update, context):
    query = update.callback_query
    query_data = query.data
    query_data_split = query_data.split()
    command = query_data_split[0]
    if command == '/busstop' or command == '/updatebusstop' or command == '/updatebusstopSortByArr':
        bus_stop_code = query_data_split[1]
        first_whitespace_idx = query_data.find(" ")
        second_whitespace_idx = query_data.find(" ", first_whitespace_idx + 1)
        bus_stop_desc = None if second_whitespace_idx == -1 else query_data[second_whitespace_idx + 1:]
        sort_strategy = ServiceArrSortStrategy() if command == '/updatebusstopSortByArr' else ServiceNoSortStrategy()
        tele_bus_arr_msg = get_tele_bus_arr_msg(bus_utils.get_bus_timings(bus_stop_code, sort_strategy), bus_stop_code, bus_stop_desc)
        if command == '/busstop': 
            await update.callback_query.message.reply_text(tele_bus_arr_msg.message, reply_markup=tele_bus_arr_msg.reply_markup,  parse_mode=constants.ParseMode.MARKDOWN, link_preview_options=LinkPreviewOptions(is_disabled=True))
        else:
            await update.callback_query.message.edit_text(tele_bus_arr_msg.message, reply_markup=tele_bus_arr_msg.reply_markup, parse_mode=constants.ParseMode.MARKDOWN, link_preview_options=LinkPreviewOptions(is_disabled=True))
    else:
        # CallbackQueries need to be answered, even if no notification to the user is needed
        # Some clients may have trouble otherwise. See https://core.telegram.org/bots/api#callbackquery
        await query.answer()

# formats response in Markdown_v2 as the llm tends to reply in markdown
async def llm_chat_handler(update, context):
    await update.message.reply_chat_action(constants.ChatAction.TYPING)
    input = update.message.text
    chat_id = update.message.from_user.id
    if not chat_id: raise Exception("Error, unable to obtain user id")
    if input == None or len(input) == 0:
        await update.message.reply_text("Please send a message")
    else:
        ai_bus_arr_card = ai_agent.handle_user_msg(input=input, chat_id=chat_id)
        tele_bus_arr_msg = get_tele_bus_arr_msg(ai_bus_arr_card.card_content, ai_bus_arr_card.bus_stop_code)
        await update.message.reply_text(tele_bus_arr_msg.message, reply_markup=tele_bus_arr_msg.reply_markup, parse_mode=constants.ParseMode.MARKDOWN, link_preview_options=LinkPreviewOptions(is_disabled=True))

# TODO: capture Exception message here
async def generic_error_handler(update, context) -> None:
    print(f"error: {context.error}")
    tb_list = traceback.format_exception(None, context.error, context.error.__traceback__)
    tb_string = "".join(tb_list)
    print(f"traceback: {tb_string}")
    if update is None or update.message is None: return
    await update.message.reply_text("Sorry, we failed to process your request")

def main():
    token = os.getenv("TELE_BOT_API_KEY")
    application = Application.builder().token(token).concurrent_updates(True).read_timeout(30).write_timeout(30).build()
    application.add_handler(CommandHandler("busstop", bus_timings_handler))
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.LOCATION, nearby_bus_stops_handler))
    application.add_handler(CallbackQueryHandler(callbackHandler))
    application.add_handler(MessageHandler(filters.TEXT, llm_chat_handler))
    application.add_error_handler(generic_error_handler)
    print("Telegram Bot started!", flush=True)
    application.run_polling()

if __name__ == "__main__":
    load_dotenv()
    lta_odata_url = os.getenv("LTA_ODATA_URL")
    lta_acc_key = os.getenv("LTA_ACC_KEY")
    gmap_url_base = os.getenv("GMAP_URL_BASE")
    bus_utils = BusUtils(lta_odata_url, lta_acc_key, gmap_url_base)
    ai_agent = AiAgent(bus_utils=bus_utils)
    main()


