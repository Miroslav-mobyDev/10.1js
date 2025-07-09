import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))
WHATSAPP_GROUP_LINK = os.getenv("WHATSAPP_GROUP_LINK")

# Conversation states
WAITING_FOR_CHECK, ASK_NAME, ASK_PHONE = range(3)

# In-memory storage (consider using a database for production)
user_attempts: Dict[int, int] = {}
user_registrations: Dict[int, Dict[str, Any]] = {}

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", 
    level=logging.INFO,
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def validate_phone_number(phone: str) -> bool:
    """Validate phone number format"""
    # Remove all non-digit characters
    cleaned_phone = re.sub(r'\D', '', phone)
    # Check if it's a valid length (7-15 digits)
    return 7 <= len(cleaned_phone) <= 15

def save_user_data(user_id: int, data: Dict[str, Any]) -> None:
    """Save user registration data"""
    user_registrations[user_id] = {
        **data,
        'registration_time': datetime.now().isoformat(),
        'user_id': user_id
    }
    
    # Log registration for admin tracking
    logger.info(f"New registration: User {user_id}, Name: {data.get('name')}, Phone: {data.get('phone')}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle errors"""
    logger.error(f"Exception while handling an update: {context.error}")
    
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "😔 Произошла ошибка. Пожалуйста, попробуйте еще раз или обратитесь к администратору."
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start command handler"""
    if not update.message:
        return ConversationHandler.END
    
    user = update.effective_user
    logger.info(f"User {user.id} (@{user.username}) started the bot")
    
    # Check if user already registered
    if user.id in user_registrations:
        await update.message.reply_text(
            f"🎉 Привет, {user_registrations[user.id].get('name', 'дорогой участник')}!\n"
            f"Ты уже зарегистрирован в марафоне.\n\n"
            f"Вот ссылка на WhatsApp-группу:\n{WHATSAPP_GROUP_LINK}"
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        "👋 Привет! Добро пожаловать в марафон восточной кухни!\n\n"
        "📌 Для участия в марафоне:\n"
        "1️⃣ Оплатите участие на Kaspi\n"
        "2️⃣ Пришлите сюда чек об оплате (фото или PDF файл)\n"
        "3️⃣ Укажите ваше имя и номер телефона\n\n"
        "После этого вы получите доступ к WhatsApp-группе марафона! 🍜"
    )
    return WAITING_FOR_CHECK

async def receive_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle receipt submission"""
    if not update.message:
        return ConversationHandler.END
    
    user_id = update.effective_user.id
    message = update.message

    # Check if user sent a file or photo
    if not (message.photo or message.document):
        await message.reply_text(
            "❌ Пожалуйста, пришлите фото чека или PDF файл.\n"
            "Если у вас есть вопросы по оплате, напишите /cancel и обратитесь к администратору."
        )
        return WAITING_FOR_CHECK

    # Track user attempts
    user_attempts[user_id] = user_attempts.get(user_id, 0) + 1
    
    # Save receipt info for admin review
    file_info = None
    if message.photo:
        file_info = message.photo[-1].file_id  # Get highest resolution photo
        file_type = "photo"
    elif message.document:
        file_info = message.document.file_id
        file_type = "document"
    
    context.user_data["receipt_file_id"] = file_info
    context.user_data["receipt_type"] = file_type

    # If user has tried too many times, send to manual review
    if user_attempts[user_id] > 2:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ ТРЕБУЕТ ПРОВЕРКИ\n"
                     f"Пользователь @{update.effective_user.username or 'unknown'} (ID: {user_id})\n"
                     f"отправил чек в {user_attempts[user_id]} раз.\n"
                     f"Файл ID: {file_info}"
            )
        except Exception as e:
            logger.error(f"Failed to send message to admin: {e}")
        
        await message.reply_text(
            "⚠️ Ваш чек передан на ручную проверку администратору.\n"
            "Мы свяжемся с вами в ближайшее время."
        )
        return ConversationHandler.END

    await message.reply_text(
        "✅ Чек получен и сохранен!\n"
        "📝 Теперь напишите, пожалуйста, ваше полное имя:"
    )
    return ASK_NAME

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle name input"""
    if not update.message:
        return ConversationHandler.END
    
    name = update.message.text.strip()
    
    # Basic name validation
    if len(name) < 2:
        await update.message.reply_text(
            "❌ Пожалуйста, введите ваше полное имя (минимум 2 символа):"
        )
        return ASK_NAME
    
    context.user_data["name"] = name
    await update.message.reply_text(
        "📱 Отлично! Теперь пришлите ваш номер телефона:\n"
        "(Например: +7 777 123 45 67 или 87771234567)"
    )
    return ASK_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle phone number input"""
    if not update.message:
        return ConversationHandler.END
    
    phone = update.message.text.strip()
    
    # Validate phone number
    if not validate_phone_number(phone):
        await update.message.reply_text(
            "❌ Пожалуйста, введите корректный номер телефона:\n"
            "(Например: +7 777 123 45 67 или 87771234567)"
        )
        return ASK_PHONE
    
    # Get user data
    name = context.user_data.get("name")
    user_id = update.effective_user.id
    username = update.effective_user.username
    
    # Save all user data
    user_data = {
        "name": name,
        "phone": phone,
        "username": username,
        "receipt_file_id": context.user_data.get("receipt_file_id"),
        "receipt_type": context.user_data.get("receipt_type")
    }
    
    save_user_data(user_id, user_data)
    
    # Notify admin about new registration
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"🎉 НОВАЯ РЕГИСТРАЦИЯ\n"
                 f"👤 Имя: {name}\n"
                 f"📱 Телефон: {phone}\n"
                 f"🆔 User ID: {user_id}\n"
                 f"📎 Username: @{username or 'не указан'}\n"
                 f"📄 Чек: {context.user_data.get('receipt_type', 'unknown')}"
        )
    except Exception as e:
        logger.error(f"Failed to notify admin about registration: {e}")
    
    # Send success message to user
    await update.message.reply_text(
        f"🎉 Отлично, {name}! Регистрация завершена!\n"
        f"📱 Ваш телефон: {phone}\n\n"
        f"🔗 Вот ссылка на WhatsApp-группу марафона:\n"
        f"{WHATSAPP_GROUP_LINK}\n\n"
        f"👩‍🍳 Старт марафона — в понедельник. Готовьтесь к кулинарным приключениям!\n"
        f"🍜 Увидимся в группе!"
    )
    
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel conversation"""
    if update.message:
        await update.message.reply_text(
            "❌ Регистрация отменена.\n"
            "Если хотите начать заново, нажмите /start"
        )
    return ConversationHandler.END

async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin command to get registration statistics"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    total_registrations = len(user_registrations)
    total_attempts = len(user_attempts)
    
    stats_text = f"📊 СТАТИСТИКА БОТА\n\n"
    stats_text += f"✅ Завершенных регистраций: {total_registrations}\n"
    stats_text += f"📝 Пользователей с попытками: {total_attempts}\n\n"
    
    if user_registrations:
        stats_text += "🔸 Последние регистрации:\n"
        sorted_registrations = sorted(
            user_registrations.items(), 
            key=lambda x: x[1]['registration_time'], 
            reverse=True
        )
        
        for user_id, data in sorted_registrations[:5]:
            stats_text += f"• {data['name']} ({data['phone']})\n"
    
    await update.message.reply_text(stats_text)

def main():
    """Main function to run the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not found in environment variables")
        return
    
    if not ADMIN_ID:
        logger.error("ADMIN_ID not found in environment variables")
        return
    
    if not WHATSAPP_GROUP_LINK:
        logger.error("WHATSAPP_GROUP_LINK not found in environment variables")
        return
    
    # Create application
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Add error handler
    app.add_error_handler(error_handler)
    
    # Create conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_CHECK: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_check),
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_check)
            ],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_message=False,
    )
    
    # Add handlers
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("stats", admin_stats))
    
    logger.info("Bot started successfully!")
    
    # Start the bot
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()