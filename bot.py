from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters

# Замените 'YOUR_BOT_TOKEN' на токен вашего бота
TOKEN = 'YOUR_BOT_TOKEN'

# Ссылка на ваш канал с отзывами
REVIEWS_CHANNEL_LINK = "https://t.me/+Qca52HCOurI0MmRi"

# --- Обработчики команд ---

async def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("Записаться на шиномонтаж", callback_data='book')],
        [InlineKeyboardButton("Наши услуги", callback_data='services')],
        [InlineKeyboardButton("Оставить отзыв", callback_data='reviews')], # Новая кнопка
        [InlineKeyboardButton("Контакты", callback_data='contacts')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Добро пожаловать! Выберите действие:', reply_markup=reply_markup)

# --- Обработчик для кнопки "Отзывы" ---
async def reviews_callback(update: Update, context):
    query = update.callback_query
    await query.answer() # Всегда отвечайте на callback_query

    text = """
Спасибо за ваш интерес к нашему шиномонтажу!

Мы ценим мнение каждого клиента. Ваши отзывы помогают нам становиться лучше и поддерживать высокий уровень сервиса.

Чтобы почитать отзывы других клиентов или оставить свой, переходите по кнопке ниже:
    """
    keyboard = [[InlineKeyboardButton("Наши отзывы и предложения", url=REVIEWS_CHANNEL_LINK)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text=text, reply_markup=reply_markup)


# --- Основная функция для запуска бота ---
def main():
    application = Application.builder().token(TOKEN).build()

    # Обработчики команд
    application.add_handler(CommandHandler("start", start))

    # Обработчики кнопок
    # Предполагаем, что у вас уже есть обработчики для 'book', 'services', 'contacts'
    application.add_handler(CallbackQueryHandler(reviews_callback, pattern='^reviews$')) # Добавляем обработчик для новой кнопки

    # Запуск бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()

