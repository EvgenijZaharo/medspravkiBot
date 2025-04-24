import re, os
from typing import Final
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    filters, ContextTypes, ConversationHandler
)

TOKEN: Final = os.getenv('API_TOKEN')
ADMIN_ID: Final = os.getenv('ADMIN_ID')


CONTACT, WAITING_FOR_REPLY = range(2)          
HELP_NAME, HELP_PHONE, HELP_TEXT = range(2, 5)   

main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📞 Связаться с нами"), KeyboardButton(text="📋 Помощь со справкой")]
    ],
    resize_keyboard=True
)

# Регулярное выражение для проверки российского номера (форматы: +7XXXXXXXXXX или 8XXXXXXXXXX)
phone_pattern = re.compile(r"^(?:\+7|8)\d{10}$")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Добро пожаловать! Чем я могу помочь?", reply_markup=main_menu)

async def contact_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✏️ Напишите сообщение, и мы свяжемся с вами.")
    return CONTACT

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    message = update.message.text

    # Кнопка для админа — ответить
    button = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_to:{user.id}")
    )

    admin_text = f"📩 Новое сообщение\nОт: @{user.username or user.first_name}\nID: {user.id}\n\n{message}"
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=button)

    await update.message.reply_text("✅ Ваше сообщение отправлено!")
    return ConversationHandler.END

async def start_reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if str(update.effective_user.id) != str(ADMIN_ID):
        await query.edit_message_text("❌ Только администратор может отвечать.")
        return ConversationHandler.END

    # Сохраняем ID пользователя, которому хотим ответить
    user_id = int(query.data.split(":")[1])
    context.user_data["reply_to_user_id"] = user_id

    await query.edit_message_text("✏️ Введите сообщение для отправки пользователю.")
    return WAITING_FOR_REPLY

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data.get("reply_to_user_id")

    if not user_id:
        await update.message.reply_text("⚠️ Ошибка: не выбран пользователь для ответа.")
        return ConversationHandler.END

    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📨 Ответ от администратора:\n\n{update.message.text}"
        )
        await update.message.reply_text("✅ Ответ отправлен пользователю.")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при отправке: {e}")

    context.user_data.clear()
    return ConversationHandler.END

async def help_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✏️ Введите, пожалуйста, ваше имя:")
    return HELP_NAME

async def handle_help_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text("⚠️ Имя не может быть пустым. Введите, пожалуйста, ваше имя:")
        return HELP_NAME
    context.user_data["help_name"] = name
    await update.message.reply_text("✏️ Введите, пожалуйста, ваш номер телефона в формате +7XXXXXXXXXX или 8XXXXXXXXXX:")
    return HELP_PHONE

async def handle_help_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not phone_pattern.fullmatch(phone):
        await update.message.reply_text("⚠️ Неверный формат номера. Введите номер в формате +7XXXXXXXXXX или 8XXXXXXXXXX:")
        return HELP_PHONE
    context.user_data["help_phone"] = phone
    await update.message.reply_text("✏️ Опишите, какая справка вам нужна:")
    return HELP_TEXT

async def handle_help_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = update.message.text.strip()
    context.user_data["help_text"] = help_text

    name = context.user_data.get("help_name")
    phone = context.user_data.get("help_phone")
    user = update.message.from_user

    # Кнопка для админа — ответить
    button = InlineKeyboardMarkup.from_button(
        InlineKeyboardButton("✉️ Ответить", callback_data=f"reply_to:{user.id}")
    )

    admin_text = (
        f"📩 Новый запрос помощи со справкой:\n"
        f"От: @{user.username or user.first_name}\n"
        f"ID: {user.id}\n"
        f"Имя: {name}\n"
        f"Номер: {phone}\n"
        f"Запрос: {help_text}"
    )
    await context.bot.send_message(chat_id=ADMIN_ID, text=admin_text, reply_markup=button)
    await update.message.reply_text("✅ Ваш запрос отправлен! Мы свяжемся с вами.", reply_markup=main_menu)
    context.user_data.clear()
    return ConversationHandler.END

# --- Команда отмены для обеих конверсаций ---
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.", reply_markup=main_menu)
    context.user_data.clear()
    return ConversationHandler.END

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print(f"Ошибка: {context.error}")

if __name__ == "__main__":
    app = Application.builder().token(TOKEN).build()

    # Конверсация "Связаться с нами"
    contact_conv = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("📞 Связаться с нами"), contact_start),
            CommandHandler("contact", contact_start)
        ],
        states={
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_contact)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Конверсация "Помощь со справкой"
    help_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("📋 Помощь со справкой"), help_start)],
        states={
            HELP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_name)],
            HELP_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_phone)],
            HELP_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_help_text)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    # Конверсация для ответа администратора
    admin_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_reply_to_user, pattern=r"^reply_to:\d+$")],
        states={WAITING_FOR_REPLY: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_reply)]},
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(contact_conv)
    app.add_handler(help_conv)
    app.add_handler(admin_conv)
    app.add_error_handler(error_handler)

    print("Бот запущен.")
    app.run_polling()
