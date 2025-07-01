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
TIMEZONE = pytz.timezone('Europe/Kiev') 

# Константы для состояний ConversationHandler
ASK_NAME, ASK_PHONE = range(2)
# Добавляем новые состояния для переноса
RESCHEDULE_SELECT_DATE, RESCHEDULE_SELECT_TIME = range(2, 4) # Начинаем с 2, чтобы не пересекалось с предыдущими

# --- КОНЕЦ КОНФИГУРАЦИИ ---


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Словарь для хранения занятых слотов (в будущем можно использовать БД)
# Формат: {дата: {время: {'user_id': ..., 'telegram_user_name': ..., 'client_name': ..., 'phone_number': ...}}}
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
        f"  Дата: {new_booking['date'].strftime('%d.%m.%Y')}\n"
        f"  Время: {new_booking['time']}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление о переносе записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет приветственное сообщение с кнопками записи и просмотра записей."""
    user = update.effective_user
    welcome_message = (
        f"Привет, {user.full_name}! 👋\n\n"
        "Я ваш помощник по шиномонтажу. "
        "Готовы записаться на удобное для вас время или посмотреть свои записи?"
    )
    keyboard = [
        [InlineKeyboardButton("Записаться на шиномонтаж", callback_data="book_appointment")],
        [InlineKeyboardButton("Мои записи", callback_data="my_bookings")] # Новая кнопка
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

async def book_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает дни для записи."""
    query = update.callback_query
    await query.answer()

    keyboard = []
    # Получаем текущую дату в заданном часовом поясе
    now_aware = datetime.datetime.now(TIMEZONE)
    today_in_tz = now_aware.date() 
    
    for i in range(7):  # Предлагаем запись на 7 дней вперед
        date = today_in_tz + datetime.timedelta(days=i)
        keyboard.append(
            [InlineKeyboardButton(date.strftime("%d.%m.%Y"), callback_data=f"select_date_{date.isoformat()}")]
        )
    
    # Кнопка назад в главное меню
    keyboard.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])

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
        # Теперь booked_slots хранит словарь, поэтому проверяем наличие ключа
        is_booked = booked_slots.get(selected_date_str, {}).get(slot_str) is not None
        
        # Проверяем, если слот в прошлом
        # Сравниваем offset-aware datetime объекты
        is_past_slot = (current_slot_datetime < now_aware - datetime.timedelta(minutes=1)) # Даем небольшую "фору"
        
        button_text = f"{slot_str}"
        if is_booked:
            button_text += " (Занято)"
        elif is_past_slot:
            button_text += " (Прошло)" 

        callback_data_prefix = "select_time"
        # Если это процесс переноса, меняем префикс callback_data
        if context.user_data.get('reschedule_mode'):
            callback_data_prefix = "reschedule_time"

        callback_data = f"{callback_data_prefix}_{selected_date_str}_{slot_str}"
        
        # Отключаем кнопку, если слот занят или в прошлом
        is_disabled = is_booked or is_past_slot

        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data if not is_disabled else "ignore")] 
        )
        # Переводим следующий слот также в offset-aware
        current_slot_datetime += interval

    # Добавляем кнопку "Назад" к выбору дня или к моим записям
    if context.user_data.get('reschedule_mode'):
        keyboard.append([InlineKeyboardButton("⬅️ Назад к моим записям", callback_data="my_bookings")])
    else:
        keyboard.append([InlineKeyboardButton("⬅️ Назад к выбору дня", callback_data="book_appointment")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"Выберите время для записи на {selected_date_naive.strftime('%d.%m.%Y')}:",
        reply_markup=reply_markup
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    """Обрабатывает выбор времени и начинает запрос имени/телефона."""
    query = update.callback_query
    await query.answer()

    if query.data == "ignore": 
        await query.answer("Это время недоступно.") 
        return ConversationHandler.END # Завершаем диалог, если нажата неактивная кнопка

    parts = query.data.split("_")
    selected_date_str = parts[2]
    selected_time_str = parts[3]
    
    # Сохраняем выбранные дату и время во временных данных пользователя (user_data)
    context.user_data['selected_date'] = selected_date_str
    context.user_data['selected_time'] = selected_time_str

    # Перепроверяем, не является ли слот прошедшим или занятым прямо перед бронированием
    selected_date_naive = datetime.date.fromisoformat(selected_date_str)
    selected_time_naive = datetime.time.fromisoformat(selected_time_str)
    selected_datetime_aware = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, selected_time_naive))

    now_aware = datetime.datetime.now(TIMEZONE)

    if selected_datetime_aware < now_aware - datetime.timedelta(minutes=1): 
        await query.edit_message_text("К сожалению, это время уже прошло. Пожалуйста, выберите другое.")
        return ConversationHandler.END
    
    if booked_slots.get(selected_date_str, {}).get(selected_time_str) is not None:
        await query.edit_message_text("К сожалению, это время уже занято. Пожалуйста, выберите другое.")
        return ConversationHandler.END

    # Если все проверки пройдены, просим имя
    await query.edit_message_text("Отлично! Теперь введите ваше имя (например, 'Иван'):")
    return ASK_NAME # Переходим в состояние ASK_NAME

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает имя пользователя и просит номер телефона."""
    user_name = update.message.text
    if not user_name:
        await update.message.reply_text("Пожалуйста, введите ваше имя корректно.")
        return ASK_NAME # Остаемся в этом состоянии, если имя пустое

    context.user_data['user_name_for_booking'] = user_name # Сохраняем имя
    await update.message.reply_text(
        "Теперь, пожалуйста, введите ваш номер телефона (например, '+380ХХХХХХХХХ') для связи. "
        "Это поможет нам подтвердить вашу запись и связаться с вами при необходимости."
    )
    return ASK_PHONE # Переходим в состояние ASK_PHONE

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает номер телефона и предлагает подтвердить запись."""
    phone_number = update.message.text
    if not phone_number:
        await update.message.reply_text("Пожалуйста, введите ваш номер телефона корректно.")
        return ASK_PHONE # Остаемся в этом состоянии, если телефон пустой

    context.user_data['phone_number'] = phone_number # Сохраняем номер телефона

    selected_date_str = context.user_data['selected_date']
    selected_time_str = context.user_data['selected_time']
    user_name = context.user_data['user_name_for_booking']
    
    confirmation_text = (
        f"Пожалуйста, проверьте данные:\n\n"
        f"📅 **Дата:** {datetime.date.fromisoformat(selected_date_str).strftime('%d.%m.%Y')}\n"
        f"⏰ **Время:** {selected_time_str}\n"
        f"👤 **Имя:** {user_name}\n"
        f"📞 **Телефон:** {phone_number}\n\n"
        "Все верно?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_booking")],
        [InlineKeyboardButton("❌ Отменить", callback_data="cancel_booking_process")] # Отмена процесса, не записи
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(confirmation_text, reply_markup=reply_markup, parse_mode='Markdown')
    return ConversationHandler.END 

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Подтверждает бронирование после проверки данных."""
    query = update.callback_query
    await query.answer()

    selected_date_str = context.user_data.get('selected_date')
    selected_time_str = context.user_data.get('selected_time')
    user_name = context.user_data.get('user_name_for_booking')
    phone_number = context.user_data.get('phone_number')
    user_id = update.effective_user.id
    telegram_user_name = update.effective_user.full_name # Имя пользователя в Telegram

    # Проверка на случай, если данные почему-то потерялись (хотя вряд ли)
    if not all([selected_date_str, selected_time_str, user_name, phone_number]):
        await query.edit_message_text("Извините, произошла ошибка. Пожалуйста, начните запись заново через /start.")
        return ConversationHandler.END

    # Финальная проверка слота перед записью
    selected_date_naive = datetime.date.fromisoformat(selected_date_str)
    selected_time_naive = datetime.time.fromisoformat(selected_time_str)
    selected_datetime_aware = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, selected_time_naive))
    now_aware = datetime.datetime.now(TIMEZONE)

    if selected_datetime_aware < now_aware - datetime.timedelta(minutes=1) or booked_slots.get(selected_date_str, {}).get(selected_time_str) is not None:
        await query.edit_message_text("К сожалению, выбранное время уже недоступно. Пожалуйста, выберите другое.")
        return ConversationHandler.END

    # Если это перенос, сначала удаляем старую запись
    old_booking_key = context.user_data.get('old_booking_key') # 'YYYY-MM-DD_HH:MM'
    old_booking_data = None
    if old_booking_key:
        old_date_str, old_time_str = old_booking_key.split('_')
        if old_date_str in booked_slots and old_time_str in booked_slots[old_date_str]:
            old_booking_data = booked_slots[old_date_str].pop(old_time_str)
            if not booked_slots[old_date_str]: # Если день стал пустым
                del booked_slots[old_date_str]
            logger.info(f"Старая запись {old_booking_key} удалена для переноса.")

    # Бронируем новый слот
    if selected_date_str not in booked_slots:
        booked_slots[selected_date_str] = {}
    
    # Сохраняем полную информацию о бронировании
    new_booking_data = {
        'user_id': user_id,
        'telegram_user_name': telegram_user_name, 
        'client_name': user_name,
        'phone_number': phone_number
    }
    booked_slots[selected_date_str][selected_time_str] = new_booking_data

    confirmation_message = (
        f"✅ Отлично, {user_name}! Ваша запись подтверждена:\n\n"
        f"📅 **Дата:** {selected_date_naive.strftime('%d.%m.%Y')}\n"
        f"⏰ **Время:** {selected_time_str}\n"
        f"📞 Мы свяжемся с вами по номеру {phone_number}.\n\n"
        "Ждем вас!"
    )
    await query.edit_message_text(confirmation_message, parse_mode='Markdown')

    # Отправляем уведомление администратору
    admin_booking_info = {
        "user_id": user_id,
        "user_name": user_name,
        "date": selected_date_naive,
        "time": selected_time_str,
        "phone_number": phone_number,
        "telegram_user_name": telegram_user_name,
        "client_name": user_name # Добавляем client_name для notify_admin_new_booking
    }

    if old_booking_data:
        # Уведомление о переносе
        old_booking_for_admin = {
            'date': datetime.date.fromisoformat(old_date_str),
            'time': old_time_str,
            'client_name': old_booking_data.get('client_name', 'Неизвестно'),
            'telegram_user_name': old_booking_data.get('telegram_user_name', 'Неизвестно'),
            'user_id': old_booking_data.get('user_id', 'Неизвестно'),
            'phone_number': old_booking_data.get('phone_number', 'Неизвестно')
        }
        await notify_admin_reschedule(context, old_booking_for_admin, admin_booking_info)
    else:
        # Уведомление о новой записи
        await notify_admin_new_booking(context, admin_booking_info)

    # Очищаем данные пользователя после успешной записи
    context.user_data.clear() 
    return ConversationHandler.END

async def cancel_booking_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс бронирования (не саму запись)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("Процесс записи отменен. Если хотите записаться снова, используйте /start.")
    context.user_data.clear() # Очищаем данные пользователя
    return ConversationHandler.END

async def cancel_booking_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий процесс записи с помощью команды /cancel."""
    await update.message.reply_text("Процесс записи отменен. Вы можете начать заново с помощью /start.")
    context.user_data.clear() # Очищаем данные пользователя
    return ConversationHandler.END

# --- НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ЗАПИСЯМИ ---

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает текущие записи пользователя."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_bookings = []
    now_aware = datetime.datetime.now(TIMEZONE)

    # Ищем записи пользователя
    for date_str, times in booked_slots.items():
        for time_str, booking_info in times.items():
            if booking_info.get('user_id') == user_id:
                booking_datetime_naive = datetime.datetime.combine(datetime.date.fromisoformat(date_str), datetime.time.fromisoformat(time_str))
                booking_datetime_aware = TIMEZONE.localize(booking_datetime_naive)
                
                # Показываем только будущие записи
                if booking_datetime_aware >= now_aware - datetime.timedelta(minutes=1): # С небольшой форой
                    user_bookings.append({
                        'date': date_str,
                        'time': time_str,
                        'info': booking_info,
                        'datetime_obj': booking_datetime_aware # Добавляем для сортировки
                    })
    
    if not user_bookings:
        keyboard = [[InlineKeyboardButton("Записаться на шиномонтаж", callback_data="book_appointment")]]
        keyboard.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("У вас пока нет активных записей. Хотите записаться?", reply_markup=reply_markup)
        return

    # Сортируем записи по дате и времени
    user_bookings.sort(key=lambda x: x['datetime_obj'])

    message_text = "Ваши текущие записи:\n\n"
    keyboard = []
    for booking in user_bookings:
        date_str = booking['date']
        time_str = booking['time']
        booking_key = f"{date_str}_{time_str}" # Уникальный ключ для записи
        
        message_text += (
            f"📅 **Дата:** {datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y')}\n"
            f"⏰ **Время:** {time_str}\n"
            f"👤 **Имя:** {booking['info'].get('client_name', 'Не указано')}\n"
            f"📞 **Телефон:** {booking['info'].get('phone_number', 'Не указан')}\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(f"❌ Отменить {time_str} {datetime.date.fromisoformat(date_str).strftime('%d.%m')}", callback_data=f"cancel_specific_booking_{booking_key}"),
            InlineKeyboardButton(f"🔄 Перенести {time_str} {datetime.date.fromisoformat(date_str).strftime('%d.%m')}", callback_data=f"reschedule_specific_booking_{booking_key}")
        ])
    
    keyboard.append([InlineKeyboardButton("⬅️ Главное меню", callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def cancel_specific_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отменяет конкретную запись."""
    query = update.callback_query
    await query.answer()

    booking_key = query.data.replace("cancel_specific_booking_", "") # YYYY-MM-DD_HH:MM
    date_str, time_str = booking_key.split('_')
    user_id = update.effective_user.id

    if date_str in booked_slots and time_str in booked_slots[date_str]:
        booking_info = booked_slots[date_str][time_str]
        
        # Проверяем, что отменяет именно тот пользователь, который бронировал
        if booking_info.get('user_id') == user_id:
            del booked_slots[date_str][time_str]
            if not booked_slots[date_str]: # Если после удаления в этот день нет записей, удаляем день
                del booked_slots[date_str]
            
            await query.edit_message_text(
                f"✅ Ваша запись на {datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y')} в {time_str} успешно отменена."
            )
            
            # Уведомляем администратора об отмене
            admin_cancellation_info = {
                'user_id': user_id,
                'telegram_user_name': update.effective_user.full_name,
                'client_name': booking_info.get('client_name', 'Не указано'),
                'phone_number': booking_info.get('phone_number', 'Не указан'),
                'date': datetime.date.fromisoformat(date_str),
                'time': time_str
            }
            await notify_admin_cancellation(context, admin_cancellation_info)

        else:
            await query.edit_message_text("Вы не можете отменить эту запись, так как она сделана не вами.")
    else:
        await query.edit_message_text("Эта запись не найдена или уже отменена.")
    
    # После отмены показываем обновленный список записей
    await my_bookings(update, context) # Вызываем my_bookings для обновления списка

async def reschedule_specific_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Начинает процесс переноса конкретной записи."""
    query = update.callback_query
    await query.answer()

    booking_key = query.data.replace("reschedule_specific_booking_", "") # YYYY-MM-DD_HH:MM
    date_str, time_str = booking_key.split('_')
    user_id = update.effective_user.id

    if date_str in booked_slots and time_str in booked_slots[date_str]:
        booking_info = booked_slots[date_str][time_str]
        
        if booking_info.get('user_id') == user_id:
            # Сохраняем информацию о старой записи и включаем режим переноса
            context.user_data['old_booking_key'] = booking_key
            context.user_data['reschedule_mode'] = True
            context.user_data['user_name_for_booking'] = booking_info.get('client_name')
            context.user_data['phone_number'] = booking_info.get('phone_number')

            await query.edit_message_text(
                f"Вы переносите запись на {datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y')} в {time_str}.\n"
                "Теперь выберите новую дату и время:"
            )
            # Перенаправляем на выбор даты, как при обычной записи
            await book_appointment(update, context)
            return RESCHEDULE_SELECT_DATE # Возвращаем состояние для ConversationHandler, если он будет использоваться
        else:
            await query.edit_message_text("Вы не можете перенести эту запись, так как она сделана не вами.")
    else:
        await query.edit_message_text("Эта запись не найдена или уже отменена.")
    
    # Если не удалось начать перенос, возвращаемся к моим записям
    await my_bookings(update, context)


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возвращает пользователя в главное меню."""
    query = update.callback_query
    await query.answer()
    context.user_data.clear() # Очищаем все временные данные
    await start(update, context) # Вызываем функцию start для отображения главного меню

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

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(book_appointment, pattern="^book_appointment$"))
    application.add_handler(CallbackQueryHandler(select_date, pattern="^select_date_"))
    application.add_handler(CallbackQueryHandler(my_bookings, pattern="^my_bookings$")) # Новый обработчик
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$")) # Новый обработчик
    application.add_handler(CallbackQueryHandler(cancel_specific_booking, pattern="^cancel_specific_booking_")) # Новый обработчик
    application.add_handler(CallbackQueryHandler(reschedule_specific_booking, pattern="^reschedule_specific_booking_")) # Новый обработчик
    
    # ConversationHandler для процесса новой записи
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(select_time, pattern="^select_time_")], # Начинаем диалог по выбору времени
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], # Состояние ожидания имени
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)], # Состояние ожидания телефона
        },
        fallbacks=[CommandHandler("cancel", cancel_booking_command), CallbackQueryHandler(cancel_booking_process, pattern="^cancel_booking_process$")], # Обработчик отмены из любого состояния
    )
    application.add_handler(conv_handler)

    # ConversationHandler для процесса переноса (переиспользуем часть логики)
    # Entry point для переноса будет находиться в reschedule_specific_booking,
    # которая затем вызывает book_appointment и select_date с флагом reschedule_mode.
    # Фактически, мы начинаем новый процесс выбора даты/времени,
    # а затем он переходит в обычный ASK_NAME/ASK_PHONE.
    # Поэтому отдельный ConversationHandler здесь не нужен, если мы просто переиспользуем ASK_NAME/ASK_PHONE.
    # Но для чистоты, если бы логика переноса была сложнее, он бы пригодился.
    # В текущей реализации, после выбора новой даты/времени, процесс идет через confirm_booking,
    # которая проверяет old_booking_key и выполняет перенос.

    # Обработчики для кнопок подтверждения/отмены, которые срабатывают после завершения ConversationHandler
    application.add_handler(CallbackQueryHandler(confirm_booking, pattern="^confirm_booking$"))
    # CallbackQueryHandler(cancel_booking_process, pattern="^cancel_booking_process$") уже добавлен в fallbacks conv_handler
    
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, echo)) # Остальные текстовые сообщения

    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()

