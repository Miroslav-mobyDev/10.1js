import os
import re
import logging
from dotenv import load_dotenv
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
    ConversationHandler,
    CallbackQueryHandler,
)

# Загружаем переменные окружения из .env файла
load_dotenv()

# Используем переменные окружения для безопасности
BOT_TOKEN = os.getenv("BOT_TOKEN", "8016682643:AAF6rnAmFgkjWrtYJRk4Tg8uv_Jgzqk3iKg")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
WHATSAPP_GROUP_LINK = os.getenv("WHATSAPP_GROUP_LINK", "https://chat.whatsapp.com/your-group-link")

# Состояния разговора
WAITING_FOR_CHECK, WAITING_FOR_APPROVAL, ASK_NAME, ASK_PHONE = range(4)

# Хранение данных пользователей
user_attempts = {}
pending_approvals = {}  # user_id: {"name": "", "phone": "", "check_message_id": ""}
user_states = {}  # user_id: current_state

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Стартовая команда с кнопками для удобства"""
    if not update.message:
        return

    user_id = update.effective_user.id
    user_states[user_id] = WAITING_FOR_CHECK

    keyboard = [
        [InlineKeyboardButton("📄 Отправить чек", callback_data="send_check")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")],
        [InlineKeyboardButton("🔄 Начать заново", callback_data="restart")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    welcome_text = (
        "👋 Привет! Добро пожаловать в марафон восточной кухни!\n\n"
        "📋 **Порядок действий:**\n"
        "1️⃣ Оплатите участие на Kaspi\n"
        "2️⃣ Отправьте сюда чек об оплате (фото или PDF)\n"
        "3️⃣ Дождитесь подтверждения оплаты\n"
        "4️⃣ Заполните свои данные\n"
        "5️⃣ Получите ссылку на WhatsApp-группу\n\n"
        "Нажмите кнопку ниже, чтобы начать:"
    )

    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')
    return WAITING_FOR_CHECK

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда помощи"""
    help_text = (
        "🆘 **Помощь по использованию бота**\n\n"
        "**Команды:**\n"
        "/start - Начать регистрацию\n"
        "/help - Показать эту справку\n"
        "/cancel - Отменить текущее действие\n"
        "/status - Проверить статус заявки\n\n"
        "**Проблемы?**\n"
        "Если возникли вопросы, обратитесь к администратору."
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(help_text, parse_mode='Markdown')
    else:
        await update.message.reply_text(help_text, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    if query.data == "send_check":
        await query.edit_message_text(
            "📄 Пришлите чек об оплате (фото или PDF файл):\n\n"
            "⚠️ **Важно:** Чек должен быть четким и читаемым!"
        )
        return WAITING_FOR_CHECK
    elif query.data == "help":
        await help_command(update, context)
        return user_states.get(update.effective_user.id, WAITING_FOR_CHECK)
    elif query.data == "restart":
        user_id = update.effective_user.id
        if user_id in pending_approvals:
            del pending_approvals[user_id]
        if user_id in user_attempts:
            del user_attempts[user_id]
        return await start(update, context)

async def receive_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и проверка чека"""
    if not update.message:
        return

    user_id = update.effective_user.id
    username = update.effective_user.username or "Нет username"
    first_name = update.effective_user.first_name or "Неизвестно"
    message = update.message

    # Проверяем, что прислали файл или фото
    if not (message.photo or message.document):
        keyboard = [[InlineKeyboardButton("📄 Отправить чек", callback_data="send_check")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await message.reply_text(
            "❌ Пожалуйста, пришлите файл или фото чека.\n"
            "Принимаются: фотографии, PDF, изображения.",
            reply_markup=reply_markup
        )
        return WAITING_FOR_CHECK

    # Проверяем размер файла (если это документ)
    if message.document and message.document.file_size > 20 * 1024 * 1024:  # 20MB
        await message.reply_text("❌ Файл слишком большой. Максимальный размер: 20MB")
        return WAITING_FOR_CHECK

    try:
        # Отправляем чек админу на проверку
        admin_text = (
            f"📋 **Новый чек на проверку**\n\n"
            f"👤 Пользователь: {first_name}\n"
            f"🆔 Username: @{username}\n"
            f"🔢 ID: `{user_id}`\n\n"
            f"Для одобрения используйте: `/approve {user_id}`\n"
            f"Для отклонения: `/reject {user_id}`"
        )

        admin_keyboard = [
            [
                InlineKeyboardButton("✅ Одобрить", callback_data=f"approve_{user_id}"),
                InlineKeyboardButton("❌ Отклонить", callback_data=f"reject_{user_id}")
            ]
        ]
        admin_markup = InlineKeyboardMarkup(admin_keyboard)

        # Отправляем текст админу
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=admin_text,
            parse_mode='Markdown',
            reply_markup=admin_markup
        )

        # Отправляем сам чек
        if message.photo:
            await context.bot.send_photo(
                chat_id=ADMIN_ID,
                photo=message.photo[-1].file_id,
                caption=f"Чек от пользователя {first_name} (@{username})"
            )
        elif message.document:
            await context.bot.send_document(
                chat_id=ADMIN_ID,
                document=message.document.file_id,
                caption=f"Чек от пользователя {first_name} (@{username})"
            )

        # Сохраняем пользователя в ожидающие подтверждения
        pending_approvals[user_id] = {
            "username": username,
            "first_name": first_name,
            "check_sent": True
        }
        user_states[user_id] = WAITING_FOR_APPROVAL

        await message.reply_text(
            "⏳ **Чек отправлен на проверку!**\n\n"
            "Ожидайте подтверждения от администратора.\n"
            "Обычно проверка занимает до 24 часов.\n\n"
            "💡 Вы можете проверить статус командой /status"
        )

        return WAITING_FOR_APPROVAL

    except Exception as e:
        logger.error(f"Ошибка при отправке чека админу: {e}")
        await message.reply_text(
            "❌ Произошла ошибка при отправке чека на проверку.\n"
            "Попробуйте еще раз или обратитесь к администратору."
        )
        return WAITING_FOR_CHECK

async def admin_approval_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик одобрения/отклонения чеков админом"""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        await query.answer("❌ У вас нет прав для этого действия", show_alert=True)
        return

    data_parts = query.data.split("_")
    action = data_parts[0]  # approve или reject
    user_id = int(data_parts[1])

    if user_id not in pending_approvals:
        await query.edit_message_text("❌ Пользователь не найден в ожидающих")
        return

    user_data = pending_approvals[user_id]

    if action == "approve":
        # Одобряем чек
        await query.edit_message_text(
            f"✅ **Чек одобрен**\n"
            f"Пользователь: {user_data['first_name']} (@{user_data['username']})"
        )

        # Уведомляем пользователя
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ **Отлично! Ваш чек подтвержден.**\n\n"
                     "Теперь пожалуйста, введите ваше **имя**:"
            )
            # Обновляем состояние пользователя
            user_states[user_id] = ASK_NAME

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=f"⚠️ Не удалось уведомить пользователя {user_id}"
            )

    elif action == "reject":
        # Отклоняем чек
        await query.edit_message_text(
            f"❌ **Чек отклонен**\n"
            f"Пользователь: {user_data['first_name']} (@{user_data['username']})"
        )

        # Увеличиваем счетчик попыток
        user_attempts[user_id] = user_attempts.get(user_id, 0) + 1

        try:
            if user_attempts[user_id] >= 3:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ **Чек отклонен**\n\n"
                         "Вы исчерпали лимит попыток (3).\n"
                         "Обратитесь к администратору для решения вопроса."
                )
                # Удаляем из ожидающих
                del pending_approvals[user_id]
                user_states[user_id] = WAITING_FOR_CHECK
            else:
                remaining = 3 - user_attempts[user_id]
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ **Чек отклонен**\n\n"
                         f"Пожалуйста, пришлите корректный чек об оплате.\n"
                         f"Осталось попыток: {remaining}"
                )
                user_states[user_id] = WAITING_FOR_CHECK

        except Exception as e:
            logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")

async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и валидация имени"""
    if not update.message:
        return

    name = update.message.text.strip()

    # Валидация имени
    if not name:
        await update.message.reply_text("❌ Имя не может быть пустым. Попробуйте еще раз:")
        return ASK_NAME

    if len(name) < 2:
        await update.message.reply_text("❌ Имя слишком короткое (минимум 2 символа):")
        return ASK_NAME

    if len(name) > 50:
        await update.message.reply_text("❌ Имя слишком длинное (максимум 50 символов):")
        return ASK_NAME

    # Проверяем, что имя содержит только буквы, пробелы и дефисы
    if not re.match(r"^[а-яёА-ЯЁa-zA-Z\s\-]+$", name):
        await update.message.reply_text(
            "❌ Имя может содержать только буквы, пробелы и дефисы.\n"
            "Попробуйте еще раз:"
        )
        return ASK_NAME

    context.user_data["name"] = name
    user_states[update.effective_user.id] = ASK_PHONE
    
    await update.message.reply_text(
        f"✅ Отлично, {name}!\n\n"
        "📱 Теперь пришлите ваш **номер телефона**:\n"
        "Например: +7 777 123 45 67"
    )
    return ASK_PHONE

async def receive_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение и валидация номера телефона"""
    if not update.message:
        return

    phone = update.message.text.strip()

    # Валидация телефона
    if not phone:
        await update.message.reply_text("❌ Номер телефона не может быть пустым:")
        return ASK_PHONE

    # Убираем все символы кроме цифр и +
    clean_phone = re.sub(r'[^\d+]', '', phone)

    # Проверяем формат (начинается с + и содержит 10-15 цифр)
    if not re.match(r'^\+\d{10,15}$', clean_phone):
        await update.message.reply_text(
            "❌ Неверный формат номера телефона.\n\n"
            "Используйте формат: +7 777 123 45 67\n"
            "Попробуйте еще раз:"
        )
        return ASK_PHONE

    context.user_data["phone"] = clean_phone
    name = context.user_data.get("name")
    user_id = update.effective_user.id

    # Удаляем из ожидающих подтверждения
    if user_id in pending_approvals:
        del pending_approvals[user_id]

    # Отправляем итоговое сообщение с ссылкой
    final_message = (
        f"🎉 **Регистрация завершена!**\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {clean_phone}\n\n"
        f"🔗 **Ссылка на WhatsApp-группу марафона:**\n"
        f"{WHATSAPP_GROUP_LINK}\n\n"
        f"👩‍🍳 **Старт марафона — в понедельник!**\n"
        f"Мы тебя ждем! Увидимся в группе! 🥘✨"
    )

    await update.message.reply_text(final_message, parse_mode='Markdown')

    # Уведомляем админа о новой регистрации
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=f"✅ **Новая регистрация завершена**\n\n"
                 f"👤 Имя: {name}\n"
                 f"📱 Телефон: {clean_phone}\n"
                 f"🆔 ID: {user_id}\n"
                 f"👤 Username: @{update.effective_user.username or 'Нет'}",
            parse_mode='Markdown'
        )
    except Exception as e:
        logger.error(f"Ошибка уведомления админа о регистрации: {e}")

    # Очищаем состояние пользователя
    if user_id in user_states:
        del user_states[user_id]

    return ConversationHandler.END

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка статуса заявки"""
    if not update.message:
        return

    user_id = update.effective_user.id

    if user_id in pending_approvals:
        await update.message.reply_text(
            "⏳ **Статус:** Ваш чек на проверке\n\n"
            "Ожидайте подтверждения от администратора.\n"
            "Обычно проверка занимает до 24 часов."
        )
    else:
        attempts = user_attempts.get(user_id, 0)
        if attempts > 0:
            remaining = max(0, 3 - attempts)
            await update.message.reply_text(
                f"📊 **Статус:** \n"
                f"Использовано попыток: {attempts}/3\n"
                f"Осталось попыток: {remaining}\n\n"
                f"Используйте /start для новой попытки."
            )
        else:
            await update.message.reply_text(
                "📝 **Статус:** Вы еще не отправляли чек\n\n"
                "Используйте /start для начала регистрации."
            )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена текущего действия"""
    if update.message:
        user_id = update.effective_user.id

        # Удаляем из ожидающих, если есть
        if user_id in pending_approvals:
            del pending_approvals[user_id]

        # Очищаем состояние
        if user_id in user_states:
            del user_states[user_id]

        keyboard = [[InlineKeyboardButton("🔄 Начать заново", callback_data="restart")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "❌ **Действие отменено**\n\n"
            "Вы можете начать заново когда захотите.",
            reply_markup=reply_markup
        )
    return ConversationHandler.END

# Команды для админа
async def approve_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда одобрения чека админом"""
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Использование: /approve <user_id>")
        return

    try:
        user_id = int(context.args[0])
        if user_id in pending_approvals:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ **Отлично! Ваш чек подтвержден.**\n\n"
                     "Теперь пожалуйста, введите ваше **имя**:"
            )
            user_states[user_id] = ASK_NAME
            await update.message.reply_text(f"✅ Чек пользователя {user_id} одобрен")
        else:
            await update.message.reply_text("❌ Пользователь не найден в ожидающих")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат. Используйте: /approve <user_id>")

async def reject_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда отклонения чека админом"""
    if update.effective_user.id != ADMIN_ID:
        return

    if not context.args:
        await update.message.reply_text("Использование: /reject <user_id>")
        return

    try:
        user_id = int(context.args[0])
        if user_id in pending_approvals:
            user_attempts[user_id] = user_attempts.get(user_id, 0) + 1
            remaining = max(0, 3 - user_attempts[user_id])

            if remaining > 0:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=f"❌ **Чек отклонен**\n\n"
                         f"Пожалуйста, пришлите корректный чек об оплате.\n"
                         f"Осталось попыток: {remaining}"
                )
            else:
                await context.bot.send_message(
                    chat_id=user_id,
                    text="❌ **Чек отклонен**\n\n"
                         "Вы исчерпали лимит попыток (3).\n"
                         "Обратитесь к администратору."
                )
                del pending_approvals[user_id]

            user_states[user_id] = WAITING_FOR_CHECK
            await update.message.reply_text(f"❌ Чек пользователя {user_id} отклонен")
        else:
            await update.message.reply_text("❌ Пользователь не найден в ожидающих")
    except (ValueError, IndexError):
        await update.message.reply_text("❌ Неверный формат. Используйте: /reject <user_id>")

def main():
    """Основная функция запуска бота"""
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN":
        logger.error("❌ Не установлен BOT_TOKEN!")
        return

    if ADMIN_ID == 123456789:
        logger.warning("⚠️ Используется стандартный ADMIN_ID!")

    app = Application.builder().token(BOT_TOKEN).build()

    # Обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_CHECK: [
                MessageHandler(filters.PHOTO | filters.Document.ALL, receive_check),
                CallbackQueryHandler(button_handler),
            ],
            WAITING_FOR_APPROVAL: [
                MessageHandler(filters.TEXT, lambda u, c: u.message.reply_text(
                    "⏳ Ожидайте подтверждения чека. Проверьте статус: /status"
                ))
            ],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            ASK_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_phone)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            CommandHandler("start", start),
        ],
    )

    # Добавляем обработчики
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("approve", approve_command))
    app.add_handler(CommandHandler("reject", reject_command))
    app.add_handler(CallbackQueryHandler(admin_approval_handler, pattern=r"^(approve|reject)_\d+$"))
    app.add_handler(CallbackQueryHandler(button_handler))

    logger.info("🚀 Бот запущен!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()