from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from config import API_TOKEN

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
