import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
import datetime
import os 
import pytz # Добавляем импорт pytz для работы с часовыми поясами

# --- КОНФИГУРАЦИЯ БОТА ---
# Настоятельно рекомендуется использовать переменные окружения на Railway для безопасности!
# Если переменные окружения TELEGRAM_BOT_TOKEN или ADMIN_USER_ID не установлены на Railway,
# то будут использоваться значения по умолчанию, указанные здесь.
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "7646808754:AAFEd_-JuxKF7jy4_xbRvolfDBbbCHy6Tt8") 
# Преобразуем ADMIN_USER_ID в int. Если переменной нет или она некорректна, то None.
try:
    ADMIN_CHAT_ID = int(os.environ.get("ADMIN_USER_ID", "7285220061"))
except (ValueError, TypeError):
    ADMIN_CHAT_ID = None 
    logging.warning("ADMIN_USER_ID не установлен или некорректен в переменных окружения. Уведомления админу могут не работать.")

# Определяем часовой пояс для работы бота (например, для Украины - 'Europe/Kiev')
# Важно установить правильный часовой пояс, чтобы слоты корректно отображались
TIMEZONE = pytz.timezone('Europe/Kiev') # Используем часовой пояс Киева для Одессы

# --- КОНЕЦ КОНФИГУРАЦИИ ---


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения занятых слотов (в будущем можно использовать БД)
# Формат: {дата: {время: id_пользователя}}
booked_slots = {}

async def notify_admin_new_booking(context: ContextTypes.DEFAULT_TYPE, booking_info: dict) -> None:
    """Отправляет уведомление администратору о новой брони."""
    if ADMIN_CHAT_ID is None:
        logger.warning("ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return

    message = (
        f"🔔 **НОВАЯ ЗАПИСЬ!**\n\n"
        f"**Клиент:** {booking_info['user_name']} (ID: {booking_info['user_id']})\n"
        f"**Дата:** {booking_info['date'].strftime('%d.%m.%Y')}\n"
        f"**Время:** {booking_info['time']}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление о новой записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с кнопкой записи."""
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.full_name}! 👋\n\n"
        "Я ваш помощник по шиномонтажу. "
        "Готовы записаться на удобное для вас время?"
    )
    keyboard = [[InlineKeyboardButton("Записаться на шиномонтаж", callback_data="book_appointment")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def book_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает дни для записи."""
    query = update.callback_query
    await query.answer()

    keyboard = []
    # Получаем текущую дату в заданном часовом поясе
    today_in_tz = datetime.datetime.now(TIMEZONE).date() 
    
    for i in range(7):  # Предлагаем запись на 7 дней вперед
        date = today_in_tz + datetime.timedelta(days=i)
        keyboard.append(
            [InlineKeyboardButton(date.strftime("%d.%m.%Y"), callback_data=f"select_date_{date.isoformat()}")]
        )
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text("Выберите день для записи:", reply_markup=reply_markup)

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает доступные слоты времени для выбранного дня."""
    query = update.callback_query
    await query.answer()

    selected_date_str = query.data.replace("select_date_", "")
    selected_date_naive = datetime.date.fromisoformat(selected_date_str) # Дата без TZ

    keyboard = []
    start_time = datetime.time(8, 0) # Начало работы в 8:00
    end_time = datetime.time(17, 0)  # Конец работы в 17:00
    interval = datetime.timedelta(minutes=30)

    # Получаем текущее время с учетом часового пояса
    now_aware = datetime.datetime.now(TIMEZONE)
    
    # Инициализируем первый слот как offset-aware datetime
    current_slot_datetime = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, start_time))
    
    while current_slot_datetime.time() <= end_time:
        slot_str = current_slot_datetime.strftime("%H:%M")
        
        # Проверяем, занят ли слот
        is_booked = booked_slots.get(selected_date_str, {}).get(slot_str) is not None
        
        # Проверяем, если слот в прошлом
        # Сравниваем offset-aware datetime объекты
        is_past_slot = (current_slot_datetime < now_aware - datetime.timedelta(minutes=1)) # Даем небольшую "фору"
        
        button_text = f"{slot_str}"
        if is_booked:
            button_text += " (Занято)"
        elif is_past_slot:
            button_text += " (Прошло)" 

        callback_data = f"select_time_{selected_date_str}_{slot_str}"
        
        # Отключаем кнопку, если слот занят или в прошлом
        is_disabled = is_booked or is_past_slot

        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data if not is_disabled else "ignore")] 
        )
        # Переводим следующий слот также в offset-aware
        current_slot_datetime += interval

    # Добавляем кнопку "Назад"
    keyboard.append([InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="book_appointment")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите время для записи на {selected_date_naive.strftime('%d.%m.%Y')}:",
        reply_markup=reply_markup
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает выбор времени и подтверждает запись."""
    query = update.callback_query
    await query.answer()

    if query.data == "ignore": 
        await query.answer("Это время недоступно.") 
        return

    parts = query.data.split("_")
    selected_date_str = parts[2]
    selected_time_str = parts[3]
    user_id = update.effective_user.id
    user_name = update.effective_user.full_name

    # Создаем offset-aware datetime для выбранного слота
    selected_date_naive = datetime.date.fromisoformat(selected_date_str)
    selected_time_naive = datetime.time.fromisoformat(selected_time_str)
    selected_datetime_aware = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, selected_time_naive))

    # Получаем текущее время с учетом часового пояса
    now_aware = datetime.datetime.now(TIMEZONE)

    # Проверяем, не является ли слот прошедшим или занятым прямо перед бронированием
    if selected_datetime_aware < now_aware - datetime.timedelta(minutes=1): 
        await query.edit_message_text("К сожалению, это время уже прошло. Пожалуйста, выберите другое.")
        return
    
    if booked_slots.get(selected_date_str, {}).get(selected_time_str) is not None:
        await query.edit_message_text("К сожалению, это время уже занято. Пожалуйста, выберите другое.")
        return


    # Если слот свободен и не в прошлом, бронируем
    if selected_date_str not in booked_slots:
        booked_slots[selected_date_str] = {}
    booked_slots[selected_date_str][selected_time_str] = user_id

    confirmation_message = (
        f"✅ Отлично, {user_name}! Вы успешно записаны на шиномонтаж:\n\n"
        f"📅 **Дата:** {selected_date_naive.strftime('%d.%m.%Y')}\n"
        f"⏰ **Время:** {selected_time_str}\n\n"
        "Ждем вас!"
    )
    await query.edit_message_text(confirmation_message, parse_mode='Markdown')

    # Отправляем уведомление администратору
    booking_info = {
        "user_id": user_id,
        "user_name": user_name,
        "date": selected_date_naive,
        "time": selected_time_str
    }
    await notify_admin_new_booking(context, booking_info)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с помощью."""
    await update.message.reply_text("Используйте команду /start для начала работы с ботом.")

async def echo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Повторяет текстовые сообщения пользователя."""
    await update.message.reply_text(update.message.text)


def main() -> None:
    """Запускает бота."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Exiting.")
        return

    application = Application.builder().token(BOT_TOKEN).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(book_appointment, pattern="^book_appointment$"))
    application.add_handler(CallbackQueryHandler(select_date, pattern="^select_date_"))
    application.add_handler(CallbackQueryHandler(select_time, pattern="^select_time_"))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo))

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
