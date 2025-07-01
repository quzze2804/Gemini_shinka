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
    JobQueue # Убедитесь, что это импортировано
)
import datetime
import os
import pytz

# --- КОНФИГУРАЦИЯ БОТА ---
# Используйте переменную окружения TELEGRAM_BOT_TOKEN
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN") 

try:
    # Используйте переменную окружения TELEGRAM_ADMIN_CHAT_ID (как вы её назвали в Railway)
    # Если переменная окружения не установлена, будет использоваться значение по умолчанию (ваш ID)
    ADMIN_CHAT_ID = int(os.environ.get("TELEGRAM_ADMIN_CHAT_ID", "7285220061")) 
except (ValueError, TypeError):
    ADMIN_CHAT_ID = None
    logging.warning("TELEGRAM_ADMIN_CHAT_ID не установлен или некорректен в переменных окружения. Уведомления админу могут не работать.")

TIMEZONE = pytz.timezone('Europe/Kiev') 

# Константы для состояний ConversationHandler
ASK_NAME, ASK_PHONE = range(2)
RESCHEDULE_SELECT_DATE, RESCHEDULE_SELECT_TIME = range(2, 4) 

# --- НОВАЯ КОНСТАНТА ДЛЯ ССЫЛКИ НА КАНАЛ ОТЗЫВОВ ---
REVIEWS_CHANNEL_LINK = "https://t.me/+Qca52HCOurI0MmRi"

# --- КОНЕЦ КОНФИГУРАЦИИ ---


# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# booked_slots теперь хранит уникальные идентификаторы бронирований
# Формат: { "YYYY-MM-DD": { "HH:MM": { ..., "job_name": "unique_job_id" } } }
booked_slots = {}

# --- СЛОВАРЬ ПЕРЕВОДОВ ---
# Все тексты бота собраны здесь для удобства перевода и выбора языка
translations = {
    'ru': {
        'choose_language': "Пожалуйста, выберите язык:\nБудь ласка, оберіть мову:",
        'lang_button_ru': "Русский",
        'lang_button_uk': "Українська",
        'welcome_message': (
            "Привет, {user_full_name}! 👋\n\n"
            "Добро пожаловать в мир комфортного и быстрого шиномонтажа!\n"
            "Я — ваш личный помощник, созданный для того, чтобы забота о шинах вашего автомобиля была максимально *удобной и беззаботной*. ✨\n\n"
            "Забудьте об очередях и звонках! С моей помощью вы можете:\n"
            "🗓️ **Быстро записаться** на удобное время.\n"
            "📋 **Проверить или перенести** свои записи.\n"
            "ℹ️ **Получить всю необходимую информацию** о наших услугах.\n\n"
            "Готовы привести свои шины в порядок?\n"
            "Выберите действие ниже, чтобы начать!"
        ),
        'btn_book_appointment': "🗓️ Записаться на шиномонтаж",
        'btn_my_bookings': "📋 Мои записи",
        'btn_info_and_faq': "ℹ️ Информация и FAQ",
        'btn_our_location': "📍 Наше местоположение",
        'btn_main_menu': "⬅️ Главное меню",
        # --- НОВЫЕ ПЕРЕВОДЫ ДЛЯ ОТЗЫВОВ ---
        'btn_reviews': "⭐ Отзывы",
        'reviews_message': (
            "Спасибо за ваш интерес к нашему шиномонтажу!\n\n"
            "Мы ценим мнение каждого клиента. Ваши отзывы помогают нам становиться лучше и поддерживать высокий уровень сервиса.\n\n"
            "Чтобы почитать отзывы других клиентов или оставить свой, переходите по кнопке ниже:"
        ),
        'btn_go_to_reviews_channel': "Наши отзывы и предложения",
        # --- КОНЕЦ НОВЫХ ПЕРЕВОДОВ ---
        'select_day_for_booking': "Выберите день для записи:",
        'select_time_for_booking': "Выберите время для записи на {date}:",
        'time_unavailable': "Это время недоступно.",
        'time_passed': "К сожалению, это время уже прошло. Пожалуйста, выберите другое.",
        'time_booked': "К сожалению, это время уже занято. Пожалуйста, выберите другое.",
        'enter_name': "Отлично! Теперь введите ваше имя (например, 'Иван'):",
        'name_incorrect': "Пожалуйста, введите ваше имя корректно.",
        'enter_phone': (
            "Теперь, пожалуйста, введите ваш номер телефона (например, '+380ХХХХХХХХХ') для связи. "
            "Это поможет нам подтвердить вашу запись и связаться с вами при необходимости."
        ),
        'phone_incorrect': "Пожалуйста, введите ваш номер телефона корректно.",
        'check_data': "Пожалуйста, проверьте данные:",
        'date_label': "Дата:",
        'time_label': "Время:",
        'name_label': "Имя:",
        'phone_label': "Телефон:",
        'all_correct': "Все верно?",
        'btn_confirm': "✅ Подтвердить",
        'btn_cancel_process': "❌ Отменить",
        'error_try_again': "Извините, произошла ошибка. Пожалуйста, начните запись заново через /start.",
        'booking_confirmed': (
            "✅ Отлично, {user_name}! Ваша запись подтверждена:\n\n"
            "📅 **Дата:** {date_formatted}\n"
            "⏰ **Время:** {time}\n"
            "📞 Мы свяжемся с вами по номеру {phone_number}.\n\n"
            "Ждем вас!"
        ),
        'process_cancelled': "Процесс записи отменен. Если хотите записаться снова, используйте /start.",
        'no_active_bookings': "У вас пока нет активных записей. Хотите записаться?",
        'your_current_bookings': "Ваши текущие записи:\n\n",
        'btn_cancel_booking': "❌ Отменить {time} {date}",
        'btn_reschedule_booking': "🔄 Перенести {time} {date}",
        'not_your_booking_cancel': "Вы не можете отменить эту запись, так как она сделана не вами.",
        'booking_not_found': "Эта запись не найдена или уже отменена.",
        'booking_cancelled_success': "✅ Ваша запись на {date_formatted} в {time} успешно отменена.",
        'reschedule_intro': (
            "Вы переносите запись на {old_date_formatted} в {old_time}.\n"
            "Теперь выберите новую дату и время:"
        ),
        'not_your_booking_reschedule': "Вы не можете перенести эту запись, так как она сделана не вами.",
        'faq_title': "**О нашем шиномонтаже:**",
        'faq_text': (
            "Мы предоставляем полный спектр услуг по шиномонтажу для легковых автомобилей. "
            "Быстро, качественно, с гарантией!\n\n"
            "**Часто задаваемые вопросы (FAQ):**\n\n"
            "**❓ Какие услуги вы предлагаете?**\n"
            "✅ Мы выполняем монтаж/демонтаж шин, балансировку колес, ремонт проколов, сезонную смену резины, и проверку давления.\n\n"
            "**❓ Какова стоимость услуг?**\n"
            "✅ Стоимость зависит от типа вашего автомобиля и размера колес. Примерные цены:\n"
            "  - Смена резины R13-R15: от 400 грн\n"
            "  - Смена резины R16-R18: от 600 грн\n"
            "  - Балансировка: от 100 грн/колесо\n"
            "  - Ремонт прокола: от 150 грн\n"
            "Для точной оценки свяжитесь с нами или приезжайте на консультацию!\n\n"
            "**❓ Сколько времени занимает шиномонтаж?**\n"
            "✅ Обычно полная смена комплекта шин занимает от 30 до 60 минут. Ремонт одного колеса - 15-30 минут.\n\n"
            "**❓ Могу ли я приехать без записи?**\n"
            "✅ Да, можете, но мы не можем гарантировать быстрое обслуживание. Для вашего удобства рекомендуем записываться через бота.\n\n"
            "**❓ Что делать, если я опаздываю?**\n"
            "✅ Пожалуйста, сообщите нам как можно скорее! Если вы опаздываете более чем на 15 минут, ваша запись может быть перенесена.\n\n"
            "**График работы:**\n"
            "Пн-Пт: 08:00 - 17:00\n"
            "Сб-Вс: Выходной"
        ),
        'our_location_address': "Мы находимся по адресу: г. Одесса, ул. Успенская, 1 (это примерный адрес, замените на свой!)\n\n",
        'help_message': "Используйте команду /start для начала работы с ботом.",
        'admin_new_booking': (
            "🔔 **НОВАЯ ЗАПИСЬ!**\n\n"
            "**Клиент:** {client_name} (Telegram: {telegram_user_name}, ID: {user_id})\n"
            "**Номер телефона:** {phone_number}\n"
            "**Дата:** {date_formatted}\n"
            "**Время:** {time}"
        ),
        'admin_cancellation': (
            "❌ **ОТМЕНА ЗАПИСИ!**\n\n"
            "**Клиент:** {client_name} (Telegram: {telegram_user_name}, ID: {user_id})\n"
            "**Номер телефона:** {phone_number}\n"
            "**Отменена дата:** {date_formatted}\n"
            "**Отменено время:** {time}"
        ),
        'admin_reschedule': (
            "🔄 **ПЕРЕНОС ЗАПИСИ!**\n\n"
            "**Клиент:** {client_name} (Telegram: {telegram_user_name}, ID: {user_id})\n"
            "**Номер телефона:** {phone_number}\n\n"
            "**Старая запись:**\n"
            "  Дата: {old_date_formatted}\n"
            "  Время: {old_time}\n\n"
            "**Новая запись:**\n"
            "  Дата: {new_date_formatted}\n"
            "  Время: {new_time}"
        ),
        'not_specified': "Не указано",
        'not_specified_phone': "Не указан",
        'unknown': "Неизвестно",
        'past_slot': " (Прошло)",
        'booked_slot': " (Занято)",
        'back_to_day_select': "⬅️ Назад к выбору дня",
        'back_to_my_bookings': "⬅️ Назад к моим записям",
        'reminder_message': "🔔 Напоминание о записи! Ваша запись на шиномонтаж завтра, {date_formatted} в {time}. Ждем вас!",
        'rescheduled_successfully_message': "✅ Ваша запись успешно перенесена на {date_formatted} в {time}."
    },
    'uk': {
        'choose_language': "Будь ласка, оберіть мову:\nPlease choose your language:",
        'lang_button_ru': "Російська",
        'lang_button_uk': "Українська",
        'welcome_message': (
            "Привіт, {user_full_name}! 👋\n\n"
            "Ласкаво просимо у світ комфортного та швидкого шиномонтажу!\n"
            "Я — ваш особистий помічник, створений для того, щоб турбота про шини вашого автомобіля була максимально *зручною та безтурботною*. ✨\n\n"
            "Забудьте про черги та дзвінки! З моєю допомогою ви можете:\n"
            "🗓️ **Швидко записатися** на зручний час.\n"
            "📋 **Перевірити або перенести** свої записи.\n"
            "ℹ️ **Отримати всю необхідну інформацію** про наші послуги.\n\n"
            "Готові привести свої шини до ладу?\n"
            "Оберіть дію нижче, щоб розпочати!"
        ),
        'btn_book_appointment': "🗓️ Записатися на шиномонтаж",
        'btn_my_bookings': "📋 Мої записи",
        'btn_info_and_faq': "ℹ️ Інформація та FAQ",
        'btn_our_location': "📍 Наше місцезнаходження",
        'btn_main_menu': "⬅️ Головне меню",
        # --- НОВЫЕ ПЕРЕВОДЫ ДЛЯ ОТЗЫВОВ ---
        'btn_reviews': "⭐ Відгуки",
        'reviews_message': (
            "Дякуємо за ваш інтерес до нашого шиномонтажу!\n\n"
            "Ми цінуємо думку кожного клієнта. Ваші відгуки допомагають нам ставати кращими та підтримувати високий рівень сервісу.\n\n"
            "Щоб почитати відгуки інших клієнтів або залишити свій, переходьте за кнопкою нижче:"
        ),
        'btn_go_to_reviews_channel': "Наші відгуки та пропозиції",
        # --- КОНЕЦ НОВЫХ ПЕРЕВОДОВ ---
        'select_day_for_booking': "Оберіть день для запису:",
        'select_time_for_booking': "Оберіть час для запису на {date}:",
        'time_unavailable': "Цей час недоступний.",
        'time_passed': "На жаль, цей час вже минув. Будь ласка, оберіть інший.",
        'time_booked': "На жаль, цей час вже зайнятий. Будь ласка, оберіть інший.",
        'enter_name': "Чудово! Тепер введіть ваше ім'я (наприклад, 'Іван'):",
        'name_incorrect': "Будь ласка, введіть ваше ім'я коректно.",
        'enter_phone': (
            "Тепер, будь ласка, введіть ваш номер телефону (наприклад, '+380ХХХХХХХХХ') для зв'язку. "
            "Це допоможе нам підтвердити ваш запис та зв'язатися з вами за необхідності."
        ),
        'phone_incorrect': "Будь ласка, введіть ваш номер телефону коректно.",
        'check_data': "Будь ласка, перевірте дані:",
        'date_label': "Дата:",
        'time_label': "Час:",
        'name_label': "Ім'я:",
        'phone_label': "Телефон:",
        'all_correct': "Все вірно?",
        'btn_confirm': "✅ Підтвердити",
        'btn_cancel_process': "❌ Скасувати",
        'error_try_again': "Вибачте, сталася помилка. Будь ласка, розпочніть запис заново через /start.",
        'booking_confirmed': (
            "✅ Чудово, {user_name}! Ваш запис підтверджено:\n\n"
            "📅 **Дата:** {date_formatted}\n"
            "⏰ **Час:** {time}\n"
            "📞 Ми зв'яжемося з вами за номером {phone_number}.\n\n"
            "Чекаємо на вас!"
        ),
        'process_cancelled': "Процес запису скасовано. Якщо бажаєте записатися знову, скористайтеся /start.",
        'no_active_bookings': "У вас поки що немає активних записів. Бажаєте записатися?",
        'your_current_bookings': "Ваші поточні записи:\n\n",
        'btn_cancel_booking': "❌ Скасувати {time} {date}",
        'btn_reschedule_booking': "🔄 Перенести {time} {date}",
        'not_your_booking_cancel': "Ви не можете скасувати цей запис, оскільки його зроблено не вами.",
        'booking_not_found': "Цей запис не знайдено або його вже скасовано.",
        'booking_cancelled_success': "✅ Ваш запис на {date_formatted} о {time} успішно скасовано.",
        'reschedule_intro': (
            "Ви переносите запис на {old_date_formatted} о {old_time}.\n"
            "Тепер оберіть нову дату та час:"
        ),
        'not_your_booking_reschedule': "Ви не можете перенести цей запис, оскільки його зроблено не вами.",
        'faq_title': "**Про наш шиномонтаж:**",
        'faq_text': (
            "Ми надаємо повний спектр послуг з шиномонтажу для легкових автомобілів. "
            "Швидко, якісно, з гарантією!\n\n"
            "**Часті запитання (FAQ):**\n\n"
            "**❓ Які послуги ви пропонуєте?**\n"
            "✅ Ми виконуємо монтаж/демонтаж шин, балансування коліс, ремонт проколів, сезонну зміну гуми та перевірку тиску.\n\n"
            "**❓ Яка вартість послуг?**\n"
            "✅ Вартість залежить від типу вашого автомобіля та розміру коліс. Орієнтовні ціни:\n"
            "  - Зміна гуми R13-R15: від 400 грн\n"
            "  - Зміна гуми R16-R18: від 600 грн\n"
            "  - Балансування: від 100 грн/колесо\n"
            "  - Ремонт проколу: від 150 грн\n"
            "Для точної оцінки зв'яжіться з нами або приїжджайте на консультацію!\n\n"
            "**❓ Скільки часу займає шиномонтаж?**\n"
            "✅ Зазвичай повна зміна комплекту шин займає від 30 до 60 хвилин. Ремонт одного колеса – 15-30 хвилин.\n\n"
            "**❓ Чи можу я приїхати без запису?**\n"
            "✅ Так, можете, але ми не можемо гарантувати швидке обслуговування. Для вашої зручності рекомендуємо записуватися через бота.\n\n"
            "**❓ Що робити, якщо я запізнюся?**\n"
            "✅ Будь ласка, повідомте нам якомога швидше! Якщо ви запізнюєтеся більш ніж на 15 хвилин, ваш запис може бути перенесено."
            "**Графік роботи:**\n"
            "Пн-Пт: 08:00 - 17:00\n"
            "Сб-Нд: Вихідний"
        ),
        'our_location_address': "Ми знаходимося за адресою: м. Одеса, вул. Успенська, 1 (це приблизна адреса, замініть на свою!)\n\n",
        'help_message': "Використайте команду /start для початку роботи з ботом.",
        'admin_new_booking': (
            "🔔 **НОВИЙ ЗАПИС!**\n\n"
            "**Клієнт:** {client_name} (Telegram: {telegram_user_name}, ID: {user_id})\n"
            "**Номер телефону:** {phone_number}\n"
            "**Дата:** {date_formatted}\n"
            "**Час:** {time}"
        ),
        'admin_cancellation': (
            "❌ **СКАСУВАННЯ ЗАПИСУ!**\n\n"
            "**Клієнт:** {client_name} (Telegram: {telegram_user_name}, ID: {user_id})\n"
            "**Номер телефону:** {phone_number}\n"
            "**Скасована дата:** {date_formatted}\n"
            "**Скасований час:** {time}" # ИСПРАВЛЕНО ЗДЕСЬ
        ),
        'admin_reschedule': (
            "🔄 **ПЕРЕНЕСЕННЯ ЗАПИСУ!**\n\n"
            "**Клієнт:** {client_name} (Telegram: {telegram_user_name}, ID: {user_id})\n"
            "**Номер телефону:** {phone_number}\n\n"
            "**Старий запис:**\n"
            "  Дата: {old_date_formatted}\n"
            "  Час: {old_time}\n\n"
            "**Новий запис:**\n"
            "  Дата: {new_date_formatted}\n"
            "  Час: {new_time}"
        ),
        'not_specified': "Не вказано",
        'not_specified_phone': "Не вказаний",
        'unknown': "Невідомо",
        'past_slot': " (Минуло)",
        'booked_slot': " (Зайнято)",
        'back_to_day_select': "⬅️ Назад до вибору дня",
        'back_to_my_bookings': "⬅️ Назад до моїх записів",
        'reminder_message': "🔔 Нагадування про запис! Ваш запис на шиномонтаж завтра, {date_formatted} о {time}. Чекаємо на вас!",
        'rescheduled_successfully_message': "✅ Ваш запис успішно перенесено на {date_formatted} о {time}."
    }
}

def get_text(context: ContextTypes.DEFAULT_TYPE, key: str, **kwargs) -> str:
    """Извлекает текст на выбранном языке."""
    user_lang = context.user_data.get('language', 'ru') # По умолчанию русский
    text = translations.get(user_lang, translations['ru']).get(key, f"_{key}_") # Запасной вариант
    return text.format(**kwargs)

# --- ОСНОВНЫЕ ФУНКЦИИ БОТА ---

async def notify_admin_new_booking(context: ContextTypes.DEFAULT_TYPE, booking_info: dict) -> None:
    """Отправляет уведомление администратору о новой брони с подробностями."""
    if ADMIN_CHAT_ID is None:
        logger.warning("TELEGRAM_ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return

    admin_context = ContextTypes.DEFAULT_TYPE(context.application, chat_id=ADMIN_CHAT_ID, user_id=ADMIN_CHAT_ID)
    admin_context.user_data['language'] = 'ru' 

    message = get_text(admin_context, 'admin_new_booking',
        client_name=booking_info.get('client_name', get_text(admin_context, 'not_specified')),
        telegram_user_name=booking_info.get('telegram_user_name', get_text(admin_context, 'not_specified')),
        user_id=booking_info['user_id'],
        phone_number=booking_info.get('phone_number', get_text(admin_context, 'not_specified_phone')),
        date_formatted=booking_info['date'].strftime('%d.%m.%Y'),
        time=booking_info['time']
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление о новой записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")

async def notify_admin_cancellation(context: ContextTypes.DEFAULT_TYPE, booking_info: dict) -> None:
    """Отправляет уведомление администратору об отмене брони."""
    if ADMIN_CHAT_ID is None:
        logger.warning("TELEGRAM_ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return

    admin_context = ContextTypes.DEFAULT_TYPE(context.application, chat_id=ADMIN_CHAT_ID, user_id=ADMIN_CHAT_ID)
    admin_context.user_data['language'] = 'ru' 

    message = get_text(admin_context, 'admin_cancellation',
        client_name=booking_info.get('client_name', get_text(admin_context, 'not_specified')),
        telegram_user_name=booking_info.get('telegram_user_name', get_text(admin_context, 'not_specified')),
        user_id=booking_info['user_id'],
        phone_number=booking_info.get('phone_number', get_text(admin_context, 'not_specified_phone')),
        date_formatted=booking_info['date'].strftime('%d.%m.%Y'),
        time=booking_info['time']
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление об отмене записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")

async def notify_admin_reschedule(context: ContextTypes.DEFAULT_TYPE, old_booking: dict, new_booking: dict) -> None:
    """Отправляет уведомление администратору о переносе брони."""
    if ADMIN_CHAT_ID is None:
        logger.warning("TELEGRAM_ADMIN_CHAT_ID не установлен, уведомление администратору не будет отправлено.")
        return
    
    admin_context = ContextTypes.DEFAULT_TYPE(context.application, chat_id=ADMIN_CHAT_ID, user_id=ADMIN_CHAT_ID)
    admin_context.user_data['language'] = 'ru' 

    message = get_text(admin_context, 'admin_reschedule',
        client_name=new_booking.get('client_name', get_text(admin_context, 'not_specified')),
        telegram_user_name=new_booking.get('telegram_user_name', get_text(admin_context, 'not_specified')),
        user_id=new_booking['user_id'],
        phone_number=new_booking.get('phone_number', get_text(admin_context, 'not_specified_phone')),
        old_date_formatted=old_booking['date'].strftime('%d.%m.%Y'),
        old_time=old_booking['time'],
        new_date_formatted=new_booking['date'].strftime('%d.%m.%Y'),
        new_time=new_booking['time']
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode='Markdown')
        logger.info(f"Уведомление о переносе записи отправлено администратору {ADMIN_CHAT_ID}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления администратору: {e}")

# --- ФУНКЦИЯ ДЛЯ ОТПРАВКИ НАПОМИНАНИЯ ---
async def send_reminder(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет напоминание о предстоящей записи."""
    job = context.job
    
    chat_id = job.data['chat_id']
    user_id = job.data['user_id']
    date_str = job.data['date_str']
    time_str = job.data['time_str']
    user_lang = job.data['language']

    reminder_context = ContextTypes.DEFAULT_TYPE(context.application, chat_id=chat_id, user_id=user_id)
    reminder_context.user_data['language'] = user_lang

    reminder_message = get_text(reminder_context, 'reminder_message', 
                                date_formatted=datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y'), 
                                time=time_str)
    try:
        await context.bot.send_message(chat_id=chat_id, text=reminder_message, parse_mode='Markdown')
        logger.info(f"Напоминание отправлено пользователю {chat_id} для записи {date_str} {time_str}")
    except Exception as e:
        logger.error(f"Ошибка при отправке напоминания пользователю {chat_id}: {e}")

# --- ФУНКЦИЯ ДЛЯ ТЕСТОВОГО НАПОМИНАНИЯ ---
async def test_reminder_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет тестовое напоминание, только для админа."""
    user_id = update.effective_user.id
    
    logger.info(f"DEBUG: test_reminder_command received. Sender user_id: {user_id}")
    logger.info(f"DEBUG: ADMIN_CHAT_ID configured: {ADMIN_CHAT_ID}")

    # Проверяем, является ли пользователь администратором
    if ADMIN_CHAT_ID is None or user_id != ADMIN_CHAT_ID:
        logger.warning(f"DEBUG: Access denied for user {user_id}. ADMIN_CHAT_ID is {ADMIN_CHAT_ID}")
        await update.message.reply_text("У вас нет прав для выполнения этой команды.")
        return

    # В PTB 22.x job_queue уже привязан к application и доступен через context.job_queue
    # Если эта проверка срабатывает, значит, что-то пошло совсем не так при инициализации Application.
    if context.job_queue is None:
        logger.error("JobQueue is None in context for test_reminder_command. This should not happen if bot started correctly with PTB 22.x.")
        await update.message.reply_text("Извините, произошла внутренняя ошибка при планировании напоминания. Пожалуйста, сообщите администратору.")
        return

    chat_id = update.effective_chat.id
    # Запланировать напоминание через 10 секунд от текущего момента
    test_time = datetime.datetime.now(TIMEZONE) + datetime.timedelta(seconds=10)
    
    # Данные, которые будут переданы в send_reminder
    test_data = {
        'chat_id': chat_id,
        'user_id': user_id,
        'date_str': test_time.strftime('%Y-%m-%d'), # Формат даты для send_reminder
        'time_str': test_time.strftime('%H:%M'),    # Формат времени для send_reminder
        'language': context.user_data.get('language', 'ru') # Используем текущий язык пользователя
    }
    
    # Уникальное имя для тестовой задачи, чтобы можно было удалить предыдущие
    job_name = f"test_reminder_job_{chat_id}"
    
    # Удаляем предыдущие тестовые напоминания для этого чата, если они есть,
    # чтобы избежать дублирования, если команду вызывают несколько раз
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal() # Удаляем старую задачу
        logger.info(f"Удалено предыдущее тестовое напоминание: {job.name}")
        
    # Планируем отправку напоминания через 10 секунд
    context.job_queue.run_once(
        send_reminder, # Функция, которую нужно вызвать
        test_time,     # Время, когда нужно вызвать функцию
        data=test_data, # Данные, которые будут переданы в функцию send_reminder через context.job.data
        name=job_name  # Имя задачи для управления (удаления, поиска)
    )
    
    await update.message.reply_text(
        f"Тестовое напоминание запланировано на {test_time.strftime('%H:%M:%S')} (через 10 секунд). Проверьте личные сообщения!"
    )
    logger.info(f"Тестовое напоминание запланировано для {chat_id}")

# --- КОНЕЦ ФУНКЦИИ ТЕСТОВОГО НАПОМИНАНИЯ ---


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Отправляет приветственное сообщение и предлагает выбрать язык,
    либо сразу переходит к главному меню, если язык выбран.
    """
    user_lang = context.user_data.get('language')

    if user_lang is None:
        keyboard = [
            [InlineKeyboardButton(translations['ru']['lang_button_ru'], callback_data="set_lang_ru")],
            [InlineKeyboardButton(translations['uk']['lang_button_uk'], callback_data="set_lang_uk")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(translations['ru']['choose_language'], reply_markup=reply_markup)
        elif update.callback_query:
            await update.callback_query.edit_message_text(translations['ru']['choose_language'], reply_markup=reply_markup)
    else:
        await show_main_menu(update, context)

async def set_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Устанавливает язык для пользователя и показывает главное меню."""
    query = update.callback_query
    await query.answer()
    
    lang_code = query.data.replace("set_lang_", "")
    context.user_data['language'] = lang_code
    
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает главное меню бота на выбранном языке."""
    user = update.effective_user
    welcome_message = get_text(context, 'welcome_message', user_full_name=user.full_name)
    
    keyboard = [
        [InlineKeyboardButton(get_text(context, 'btn_book_appointment'), callback_data="book_appointment")],
        [InlineKeyboardButton(get_text(context, 'btn_my_bookings'), callback_data="my_bookings")],
        [InlineKeyboardButton(get_text(context, 'btn_info_and_faq'), callback_data="info_and_faq")], 
        [InlineKeyboardButton(get_text(context, 'btn_our_location'), callback_data="our_location")],
        [InlineKeyboardButton(get_text(context, 'btn_reviews'), callback_data="show_reviews")] # Добавлена кнопка "Отзывы"
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.message: 
        await update.message.reply_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')
    elif update.callback_query: 
        await update.callback_query.edit_message_text(welcome_message, reply_markup=reply_markup, parse_mode='Markdown')

# --- НОВАЯ ФУНКЦИЯ ДЛЯ ОБРАБОТКИ КНОПКИ "ОТЗЫВЫ" ---
async def show_reviews(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с ссылкой на канал отзывов."""
    query = update.callback_query
    await query.answer()

    text = get_text(context, 'reviews_message')
    keyboard = [[InlineKeyboardButton(get_text(context, 'btn_go_to_reviews_channel'), url=REVIEWS_CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='Markdown')

# --- КОНЕЦ НОВОЙ ФУНКЦИИ ---


async def book_appointment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает дни для записи."""
    query = update.callback_query
    await query.answer()

    keyboard = []
    now_aware = datetime.datetime.now(TIMEZONE)
    today_in_tz = now_aware.date() 
    
    for i in range(7):  
        date = today_in_tz + datetime.timedelta(days=i)
        keyboard.append(
            [InlineKeyboardButton(date.strftime("%d.%m.%Y"), callback_data=f"select_date_{date.isoformat()}")]
        )
    
    keyboard.append([InlineKeyboardButton(get_text(context, 'btn_main_menu'), callback_data="main_menu")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(get_text(context, 'select_day_for_booking'), reply_markup=reply_markup)

async def select_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает доступные слоты времени для выбранного дня."""
    query = update.callback_query
    await query.answer()

    selected_date_str = query.data.replace("select_date_", "")
    selected_date_naive = datetime.date.fromisoformat(selected_date_str) 

    keyboard = []
    start_time = datetime.time(8, 0) 
    end_time = datetime.time(17, 0)  
    interval = datetime.timedelta(minutes=30)

    now_aware = datetime.datetime.now(TIMEZONE)
    
    current_slot_datetime = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, start_time))
    
    while current_slot_datetime.time() <= end_time:
        slot_str = current_slot_datetime.strftime("%H:%M")
        
        is_booked = booked_slots.get(selected_date_str, {}).get(slot_str) is not None
        
        is_past_slot = (current_slot_datetime < now_aware - datetime.timedelta(minutes=1)) 
        
        button_text = f"{slot_str}"
        if is_booked:
            button_text += get_text(context, 'booked_slot')
        elif is_past_slot:
            button_text += get_text(context, 'past_slot') 

        callback_data = f"select_time_{selected_date_str}_{slot_str}"
        
        is_disabled = is_booked or is_past_slot

        keyboard.append(
            [InlineKeyboardButton(button_text, callback_data=callback_data if not is_disabled else "ignore")] 
        )
        current_slot_datetime += interval

    if context.user_data.get('reschedule_mode'):
        keyboard.append([InlineKeyboardButton(get_text(context, 'back_to_my_bookings'), callback_data="my_bookings")])
    else:
        keyboard.append([InlineKeyboardButton(get_text(context, 'back_to_day_select'), callback_data="book_appointment")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        get_text(context, 'select_time_for_booking', date=selected_date_naive.strftime('%d.%m.%Y')),
        reply_markup=reply_markup
    )

async def select_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    """Обрабатывает выбор времени и начинает запрос имени/телефона."""
    query = update.callback_query
    await query.answer()

    if query.data == "ignore": 
        await query.answer(get_text(context, 'time_unavailable')) 
        return ConversationHandler.END 

    parts = query.data.split("_")
    selected_date_str = parts[2]
    selected_time_str = parts[3]
    
    context.user_data['selected_date'] = selected_date_str
    context.user_data['selected_time'] = selected_time_str

    selected_date_naive = datetime.date.fromisoformat(selected_date_str)
    selected_time_naive = datetime.time.fromisoformat(selected_time_str)
    selected_datetime_aware = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, selected_time_naive))

    now_aware = datetime.datetime.now(TIMEZONE)

    if selected_datetime_aware < now_aware - datetime.timedelta(minutes=1): 
        await query.edit_message_text(get_text(context, 'time_passed'))
        return ConversationHandler.END
    
    if booked_slots.get(selected_date_str, {}).get(selected_time_str) is not None:
        await query.edit_message_text(get_text(context, 'time_booked'))
        return ConversationHandler.END

    if context.user_data.get('reschedule_mode') and \
       context.user_data.get('user_name_for_booking') and \
       context.user_data.get('phone_number'):
        
        confirmation_text = (
            f"{get_text(context, 'check_data')}\n\n"
            f"📅 **{get_text(context, 'date_label')}** {datetime.date.fromisoformat(selected_date_str).strftime('%d.%m.%Y')}\n"
            f"⏰ **{get_text(context, 'time_label')}** {selected_time_str}\n"
            f"👤 **{get_text(context, 'name_label')}** {context.user_data['user_name_for_booking']}\n"
            f"📞 **{get_text(context, 'phone_label')}** {context.user_data['phone_number']}\n\n"
            f"{get_text(context, 'all_correct')}"
        )
        keyboard = [
            [InlineKeyboardButton(get_text(context, 'btn_confirm'), callback_data="confirm_booking")],
            [InlineKeyboardButton(get_text(context, 'btn_cancel_process'), callback_data="cancel_booking_process")] 
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(confirmation_text, reply_markup=reply_markup, parse_mode='Markdown')
        return ConversationHandler.END 
    else:
        await query.edit_message_text(get_text(context, 'enter_name'))
        return ASK_NAME 

async def get_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает имя пользователя и просит номер телефона."""
    user_name = update.message.text
    if not user_name:
        await update.message.reply_text(get_text(context, 'name_incorrect'))
        return ASK_NAME 

    context.user_data['user_name_for_booking'] = user_name 
    await update.message.reply_text(get_text(context, 'enter_phone'))
    return ASK_PHONE 

async def get_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Получает номер телефона и предлагает подтвердить запись."""
    phone_number = update.message.text
    if not phone_number:
        await update.message.reply_text(get_text(context, 'phone_incorrect'))
        return ASK_PHONE 

    context.user_data['phone_number'] = phone_number 

    selected_date_str = context.user_data['selected_date']
    selected_time_str = context.user_data['selected_time']
    user_name = context.user_data['user_name_for_booking']
    
    confirmation_text = (
        f"{get_text(context, 'check_data')}\n\n"
        f"📅 **{get_text(context, 'date_label')}** {datetime.date.fromisoformat(selected_date_str).strftime('%d.%m.%Y')}\n"
        f"⏰ **{get_text(context, 'time_label')}** {selected_time_str}\n"
        f"👤 **{get_text(context, 'name_label')}** {user_name}\n"
        f"📞 **{get_text(context, 'phone_label')}** {phone_number}\n\n"
        f"{get_text(context, 'all_correct')}"
    )
    
    keyboard = [
        [InlineKeyboardButton(get_text(context, 'btn_confirm'), callback_data="confirm_booking")],
        [InlineKeyboardButton(get_text(context, 'btn_cancel_process'), callback_data="cancel_booking_process")] 
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
    chat_id = update.effective_chat.id 
    telegram_user_name = update.effective_user.full_name 
    user_lang = context.user_data.get('language', 'ru') 

    if not all([selected_date_str, selected_time_str, user_name, phone_number]):
        await query.edit_message_text(get_text(context, 'error_try_again'))
        context.user_data.clear()
        return ConversationHandler.END

    selected_date_naive = datetime.date.fromisoformat(selected_date_str)
    selected_time_naive = datetime.time.fromisoformat(selected_time_str)
    selected_datetime_aware = TIMEZONE.localize(datetime.datetime.combine(selected_date_naive, selected_time_naive))
    now_aware = datetime.datetime.now(TIMEZONE)

    if selected_datetime_aware < now_aware - datetime.timedelta(minutes=1) or booked_slots.get(selected_date_str, {}).get(selected_time_str) is not None:
        await query.edit_message_text(get_text(context, 'time_booked')) 
        context.user_data.clear()
        return ConversationHandler.END

    old_booking_key = context.user_data.get('old_booking_key') 
    old_booking_data = None
    if old_booking_key:
        old_date_str, old_time_str = old_booking_key.split('_')
        if old_date_str in booked_slots and old_time_str in booked_slots[old_date_str]:
            old_booking_data = booked_slots[old_date_str].pop(old_time_str)
            if not booked_slots[old_date_str]: 
                del booked_slots[old_date_str]
            logger.info(f"Старая запись {old_booking_key} удалена для переноса.")
            
            job_name_to_remove = f"reminder_{old_booking_key}"
            current_jobs = context.job_queue.get_jobs_by_name(job_name_to_remove)
            for job in current_jobs:
                job.schedule_removal()
                logger.info(f"Удалено старое напоминание для {job_name_to_remove}")

    if selected_date_str not in booked_slots:
        booked_slots[selected_date_str] = {}
    
    new_booking_data = {
        'user_id': user_id,
        'telegram_user_name': telegram_user_name, 
        'client_name': user_name,
        'phone_number': phone_number,
        'language': user_lang
    }
    booked_slots[selected_date_str][selected_time_str] = new_booking_data
    
    confirmation_message = get_text(context, 'booking_confirmed',
        user_name=user_name,
        date_formatted=selected_date_naive.strftime('%d.%m.%Y'),
        time=selected_time_str,
        phone_number=phone_number
    )
    
    keyboard_after_confirm = [
        [InlineKeyboardButton(get_text(context, 'btn_my_bookings'), callback_data="my_bookings")],
        [InlineKeyboardButton(get_text(context, 'btn_main_menu'), callback_data="main_menu")] 
    ]
    reply_markup_after_confirm = InlineKeyboardMarkup(keyboard_after_confirm)

    await query.edit_message_text(confirmation_message, reply_markup=reply_markup_after_confirm, parse_mode='Markdown')

    admin_booking_info = {
        "user_id": user_id,
        "user_name": user_name,
        "date": selected_date_naive,
        "time": selected_time_str,
        "phone_number": phone_number,
        "telegram_user_name": telegram_user_name,
        "client_name": user_name 
    }

    if old_booking_data:
        old_booking_for_admin = {
            'date': datetime.date.fromisoformat(old_date_str),
            'time': old_time_str,
            'client_name': old_booking_data.get('client_name', get_text(context, 'unknown')),
            'telegram_user_name': old_booking_data.get('telegram_user_name', get_text(context, 'unknown')),
            'user_id': old_booking_data.get('user_id', get_text(context, 'unknown')),
            'phone_number': old_booking_data.get('phone_number', get_text(context, 'not_specified_phone'))
        }
        await notify_admin_reschedule(context, old_booking_for_admin, admin_booking_info)
    else:
        await notify_admin_new_booking(context, admin_booking_info)

    # Планирование напоминания за день до
    reminder_time = selected_datetime_aware - datetime.timedelta(days=1)
    if reminder_time > now_aware: # Проверяем, что время напоминания еще в будущем
        job_name = f"reminder_{selected_date_str}_{selected_time_str}"
        context.job_queue.run_once(
            send_reminder,
            reminder_time,
            data={'chat_id': chat_id, 'user_id': user_id, 'date_str': selected_date_str, 'time_str': selected_time_str, 'language': user_lang},
            name=job_name
        )
        logger.info(f"Напоминание запланировано для {job_name} на {reminder_time}")
    else:
        logger.warning(f"Напопоминание для {selected_date_str} {selected_time_str} не запланировано, так как время уже прошло.")

    context.user_data.clear() 
    return ConversationHandler.END

async def cancel_booking_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет процесс бронирования (не саму запись)."""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(get_text(context, 'process_cancelled'))
    context.user_data.clear() 
    return ConversationHandler.END

async def cancel_booking_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отменяет текущий процесс записи с помощью команды /cancel."""
    await update.message.reply_text(get_text(context, 'process_cancelled')) 
    context.user_data.clear() 
    return ConversationHandler.END

# --- НОВЫЕ ФУНКЦИИ ДЛЯ УПРАВЛЕНИЯ ЗАПИСЯМИ ---

async def my_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает текущие записи пользователя."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    user_bookings = []
    now_aware = datetime.datetime.now(TIMEZONE)

    for date_str, times in booked_slots.items():
        for time_str, booking_info in times.items():
            if booking_info.get('user_id') == user_id:
                booking_datetime_naive = datetime.datetime.combine(datetime.date.fromisoformat(date_str), datetime.time.fromisoformat(time_str))
                booking_datetime_aware = TIMEZONE.localize(booking_datetime_naive)
                
                if booking_datetime_aware >= now_aware - datetime.timedelta(minutes=1): 
                    user_bookings.append({
                        'date': date_str,
                        'time': time_str,
                        'info': booking_info,
                        'datetime_obj': booking_datetime_aware 
                    })
    
    if not user_bookings:
        keyboard = [[InlineKeyboardButton(get_text(context, 'btn_book_appointment'), callback_data="book_appointment")]]
        keyboard.append([InlineKeyboardButton(get_text(context, 'btn_main_menu'), callback_data="main_menu")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(get_text(context, 'no_active_bookings'), reply_markup=reply_markup)
        return

    user_bookings.sort(key=lambda x: x['datetime_obj'])

    message_text = get_text(context, 'your_current_bookings')
    keyboard = []
    for booking in user_bookings:
        date_str = booking['date']
        time_str = booking['time']
        booking_key = f"{date_str}_{time_str}" 
        
        message_text += (
            f"📅 **{get_text(context, 'date_label')}** {datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y')}\n"
            f"⏰ **{get_text(context, 'time_label')}** {time_str}\n"
            f"👤 **{get_text(context, 'name_label')}** {booking['info'].get('client_name', get_text(context, 'not_specified'))}\n"
            f"📞 **{get_text(context, 'phone_label')}** {booking['info'].get('phone_number', get_text(context, 'not_specified_phone'))}\n\n"
        )
        keyboard.append([
            InlineKeyboardButton(get_text(context, 'btn_cancel_booking', time=time_str, date=datetime.date.fromisoformat(date_str).strftime('%d.%m')), callback_data=f"cancel_specific_booking_{booking_key}"),
            InlineKeyboardButton(get_text(context, 'btn_reschedule_booking', time=time_str, date=datetime.date.fromisoformat(date_str).strftime('%d.%m')), callback_data=f"reschedule_specific_booking_{booking_key}")
        ])
    
    keyboard.append([InlineKeyboardButton(get_text(context, 'btn_main_menu'), callback_data="main_menu")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode='Markdown')

async def cancel_specific_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отменяет конкретную запись."""
    query = update.callback_query
    await query.answer()

    booking_key = query.data.replace("cancel_specific_booking_", "") 
    date_str, time_str = booking_key.split('_')
    user_id = update.effective_user.id

    if date_str in booked_slots and time_str in booked_slots[date_str]:
        booking_info = booked_slots[date_str][time_str]
        
        if booking_info.get('user_id') == user_id:
            del booked_slots[date_str][time_str]
            if not booked_slots[date_str]: 
                del booked_slots[date_str]
            
            await query.edit_message_text(
                get_text(context, 'booking_cancelled_success', date_formatted=datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y'), time=time_str)
            )
            
            admin_cancellation_info = {
                'user_id': user_id,
                'telegram_user_name': update.effective_user.full_name,
                'client_name': booking_info.get('client_name', get_text(context, 'not_specified')),
                'phone_number': booking_info.get('phone_number', get_text(context, 'not_specified_phone')),
                'date': datetime.date.fromisoformat(date_str),
                'time': time_str
            }
            await notify_admin_cancellation(context, admin_cancellation_info)

            job_name_to_remove = f"reminder_{booking_key}"
            current_jobs = context.job_queue.get_jobs_by_name(job_name_to_remove)
            for job in current_jobs:
                job.schedule_removal()
                logger.info(f"Удалено напоминание для отмененной записи {job_name_to_remove}")

        else:
            await query.edit_message_text(get_text(context, 'not_your_booking_cancel'))
    else:
        await query.edit_message_text(get_text(context, 'booking_not_found'))
    
    await my_bookings(update, context) 

async def reschedule_specific_booking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int: 
    """Начинает процесс переноса конкретной записи."""
    query = update.callback_query
    await query.answer()

    booking_key = query.data.replace("reschedule_specific_booking_", "")
    date_str, time_str = booking_key.split('_')
    user_id = update.effective_user.id

    if date_str in booked_slots and time_str in booked_slots[date_str]:
        booking_info = booked_slots[date_str][time_str]
        
        if booking_info.get('user_id') == user_id:
            context.user_data['old_booking_key'] = booking_key
            context.user_data['reschedule_mode'] = True
            context.user_data['user_name_for_booking'] = booking_info.get('client_name')
            context.user_data['phone_number'] = booking_info.get('phone_number')

            await query.edit_message_text(
                get_text(context, 'reschedule_intro', old_date_formatted=datetime.date.fromisoformat(date_str).strftime('%d.%m.%Y'), old_time=time_str)
            )
            await book_appointment(update, context) 
            return ConversationHandler.END 
        else:
            await query.edit_message_text(get_text(context, 'not_your_booking_reschedule'))
    else:
        await query.edit_message_text(get_text(context, 'booking_not_found'))
    
    await my_bookings(update, context)
    return ConversationHandler.END 

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Возвращает пользователя в главное меню."""
    query = update.callback_query
    await query.answer()
    context.user_data.pop('reschedule_mode', None) 
    context.user_data.pop('old_booking_key', None) 
    await show_main_menu(update, context) 

async def info_and_faq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет информацию и ответы на часто задаваемые вопросы."""
    query = update.callback_query
    await query.answer()

    faq_text = get_text(context, 'faq_title') + "\n" + get_text(context, 'faq_text')

    keyboard = [[InlineKeyboardButton(get_text(context, 'btn_main_menu'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(faq_text, reply_markup=reply_markup, parse_mode='Markdown')

async def our_location(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет геопозицию шиномонтажа."""
    query = update.callback_query
    await query.answer()

    latitude = 46.467890 
    longitude = 30.730300 
    
    address_text = get_text(context, 'our_location_address')
    
    keyboard = [[InlineKeyboardButton(get_text(context, 'btn_main_menu'), callback_data="main_menu")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await context.bot.send_message(
        chat_id=update.effective_chat.id, 
        text=address_text,
        reply_markup=reply_markup,
        parse_mode='Markdown'
    )
    await context.bot.send_location(
        chat_id=update.effective_chat.id, 
        latitude=latitude, 
        longitude=longitude
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Отправляет сообщение с помощью."""
    await update.message.reply_text(get_text(context, 'help_message'))


def main() -> None:
    """Запускает бота."""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable not set. Exiting.")
        return 

    # В PTB 22.x JobQueue автоматически привязывается к Application.
    # Больше не нужно вручную инициализировать application.job_queue = JobQueue()
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("test_reminder", test_reminder_command))
    application.add_handler(CallbackQueryHandler(set_language, pattern="^set_lang_"))
    application.add_handler(CallbackQueryHandler(book_appointment, pattern="^book_appointment$"))
    application.add_handler(CallbackQueryHandler(select_date, pattern="^select_date_"))
    application.add_handler(CallbackQueryHandler(my_bookings, pattern="^my_bookings$")) 
    application.add_handler(CallbackQueryHandler(main_menu, pattern="^main_menu$")) 
    application.add_handler(CallbackQueryHandler(cancel_specific_booking, pattern="^cancel_specific_booking_")) 
    
    application.add_handler(CallbackQueryHandler(info_and_faq, pattern="^info_and_faq$"))
    application.add_handler(CallbackQueryHandler(our_location, pattern="^our_location$"))
    application.add_handler(CallbackQueryHandler(show_reviews, pattern="^show_reviews$")) # Добавлен обработчик для кнопки "Отзывы"
    
    reschedule_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(reschedule_specific_booking, pattern="^reschedule_specific_booking_")],
        states={}, # Состояния будут управляться в book_appointment и select_time
        fallbacks=[CommandHandler("cancel", cancel_booking_command), CallbackQueryHandler(cancel_booking_process, pattern="^cancel_booking_process$")],
        map_to_parent={
            ConversationHandler.END: ConversationHandler.END 
        }
    )
    application.add_handler(reschedule_conv_handler)


    booking_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(select_time, pattern="^select_time_")], 
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_name)], 
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_phone)], 
        },
        fallbacks=[CommandHandler("cancel", cancel_booking_command), CallbackQueryHandler(cancel_booking_process, pattern="^cancel_booking_process$")], 
    )
    application.add_handler(booking_conv_handler)
    
    application.add_handler(CallbackQueryHandler(confirm_booking, pattern="^confirm_booking$"))
    
    application.add_handler(CommandHandler("help", help_command))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
