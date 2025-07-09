from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
import logging

BOT_TOKEN = "YOUR_BOT_TOKEN"  # Замените на свой токен
ADMIN_ID = 123456789          # Замените на свой Telegram ID
WHATSAPP_GROUP_LINK = "https://chat.whatsapp.com/your-group-link"

WAITING_FOR_CHECK, ASK_NAME, ASK_PHONE = range(3)
user_attempts = {}

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    await update.message.reply_text(
        "👋 Привет! Добро пожаловать в марафон восточной кухни!\n\n"
        "📌 Вот программа марафона и инструкция по оплате:\n"
        "- Оплатите участие на Kaspi\n"
        "- Затем пришлите сюда чек об оплате (фото или PDF)"
    )
    return WAITING_FOR_CHECK

async def receive_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    message = update.message

    if not (message.photo or message.document):
        await message.reply_text("❌ Пожалуйста, пришлите файл или фото чека.")
        return WAITING_FOR_CHECK

    user_attempts[user_id] = user_attempts.get(user_id, 0) + 1

    if user_attempts[user_id] > 2:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"⚠️ Пользователь @{update.effective_user.username or user_id} "
                 f"дважды отправил неверный чек. Проверь вручную."
        )
        await message.reply_text("⚠️ Мы передали чек на ручную проверку.")
        return ConversationHandler.END

    await message.reply_text("✅ Чек получен. Напишите, пожалуйста, ваше имя:")
    return ASK_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    context.user_data["name"] = update.message.text
    await update.message.reply_text("📱 Теперь пришлите ваш номер телефона:")
    return ASK_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    context.user_data["phone"] = update.message.text
    name = context.user_data.get("name")
    phone = context.user_data.get("phone")

    await update.message.reply_text(
        f"🎉 Спасибо, {name}!\n"
        f"📱 Телефон: {phone}\n\n"
        f"Вот ссылка на WhatsApp-группу марафона:\n{WHATSAPP_GROUP_LINK}\n\n"
        f"👩‍🍳 Старт марафона — в понедельник. Мы тебя ждем!"
    )
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text("❌ Действие отменено.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_CHECK: [
                MessageHandler(filters.PHOTO | filters.Document.ALL | filters.TEXT, receive_check)
            ],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    app.add_handler(conv_handler)
    app.run_polling()

if __name__ == "__main__":
    main()