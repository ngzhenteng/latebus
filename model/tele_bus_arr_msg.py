from dataclasses import dataclass
from telegram import TelegramObject

@dataclass
class TeleBusArrMsg:
    message: str
    reply_markup: TelegramObject