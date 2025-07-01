Кирилл, [1 июл. 2025 в 15:20]
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
)
import datetime
import os 
import pytz 

# --- КОНФИГУРАЦИЯ БОТА ---
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7646808754:AAFEd_-JuxKF7jy4_xbRvolfDBbbCHy6Tt8") 

try:
    ADMIN_CHAT_ID = int(os.environ.get("ADMIN_USER_ID", "7285220061"))
except (ValueError, TypeError):
    ADMIN_CHAT_ID = None 
    logging.warning("ADMIN_USER_ID не установлен или некорректен в переменных окружения. Уведомления админу могут не работать.")

TIMEZONE = pytz.timezone('Europe/Kiev') 

# Константы для состояний ConversationHandler
ASK_NAME, ASK_PHONE = range(2)
RESCHEDULE_SELECT_DATE, RESCHEDULE_SELECT_TIME = range(2, 4) 

# --- КОНЕЦ КОНФИГУРАЦИИ ---


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

booked_slots = {}

async def notify_admin_new_booking(context: ContextTypes.DEFAULT_TYPE, booking_info: dict) -> None:
    """Отправляет уведомление администратору о новой брони с подробностями."""
    if ADMIN_CHAT_ID is None:
        logger.warning("ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return

    message = (
        f"🔔 **НОВАЯ ЗАПИСЬ!**\n\n"
        f"**Клиент:** {booking_info.get('client_name', 'Не указано')} "
        f"(Telegram: {booking_info.get('telegram_user_name', 'Не указано')}, ID: {booking_info['user_id']})\n"
        f"**Номер телефона:** {booking_info.get('phone_number', 'Не указан')}\n"
        f"**Дата:** {booking_info['date'].strftime('%d.%m.%Y')}\n"
        f"**Время:** {booking_info['time']}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление о новой записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")

async def notify_admin_cancellation(context: ContextTypes.DEFAULT_TYPE, booking_info: dict) -> None:
    """Отправляет уведомление администратору об отмене брони."""
    if ADMIN_CHAT_ID is None:
        logger.warning("ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return

    message = (
        f"❌ **ОТМЕНА ЗАПИСИ!**\n\n"
        f"**Клиент:** {booking_info.get('client_name', 'Не указано')} "
        f"(Telegram: {booking_info.get('telegram_user_name', 'Не указано')}, ID: {booking_info['user_id']})\n"
        f"**Номер телефона:** {booking_info.get('phone_number', 'Не указан')}\n"
        f"**Отменена дата:** {booking_info['date'].strftime('%d.%m.%Y')}\n"
        f"**Отменено время:** {booking_info['time']}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление об отмене записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")

async def notify_admin_reschedule(context: ContextTypes.DEFAULT_TYPE, old_booking: dict, new_booking: dict) -> None:
    """Отправляет уведомление администратору о переносе брони."""
    if ADMIN_CHAT_ID is None:
        logger.warning("ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return

    message = (
        f"🔄 **ПЕРЕНОС ЗАПИСИ!**\n\n"
        f"**Клиент:** {new_booking.get('client_name', 'Не указано')} "
        f"(Telegram: {new_booking.get('telegram_user_name', 'Не указано')}, ID: {new_booking['user_id']})\n"
        f"**Номер телефона:** {new_booking.get('phone_number', 'Не указан')}\n\n"
        f"**Старая запись:**\n"
        f"  Дата: {old_booking['date'].strftime('%d.%m.%Y')}\n"
        f"  Время: {old_booking['time']}\n\n"
        f"**Новая запись:**\n"
        f"  Дата: {new_booking['date'].
