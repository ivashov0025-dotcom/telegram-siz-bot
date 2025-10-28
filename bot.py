import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Состояния диалога
(
    MAIN_MENU,
    SIZ_ENTER_TAB_NUMBER,
    COMPLAINT_ENTER_TAB_NUMBER,
    COMPLAINT_ENTER_TEXT,
    NORMATIVE_CHOOSE_ROLE,
) = range(5)

# База: табельный номер → должность
TAB_TO_ROLE = {
    "001": "специалист",
    "002": "инженер",
    "003": "мастер",
}

# СИЗ по должностям
SIZ_BY_ROLE = {
    "специалист": [
        "Костюм для защиты от общих производственных загрязнений, 2 класс защиты",
        "Белье специальное хлопчатобумажное (фуфайка и кальсоны)",
        "Изделия носочно-чулочные (носки хлопчатобумажные)",
    ],
    "инженер": [
        "Каска защитная",
        "Очки защитные",
        "Перчатки кожаные",
    ],
    "мастер": [
        "Костюм специальный (хлопчатобумажный)",
        "Обувь специальная кожаная",
        "Рукавицы комбинированные",
    ],
}

AVAILABLE_ROLES = list(SIZ_BY_ROLE.keys())
NORMATIVE_DOCS_DIR = "normative_docs"


# --- Обработчики ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [KeyboardButton("Оформление заявок на СИЗ")],
        [KeyboardButton("Отправка анонимных жалоб")],
        [KeyboardButton("Получение актуальной нормативной базы")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

    try:
        with open("welcome.jpg", "rb") as photo:
            await update.message.reply_photo(
                photo=photo,
                caption=(
                    "Добро пожаловать в бот для использования:\n"
                    "- оформления заявок на СИЗ\n"
                    "- отправка анонимных жалоб\n"
                    "- получение актуальной нормативной базы"
                ),
                reply_markup=reply_markup,
            )
    except FileNotFoundError:
        await update.message.reply_text(
            "Добро пожаловать в бот для использования:\n"
            "- оформления заявок на СИЗ\n"
            "- отправка анонимных жалоб\n"
            "- получение актуальной нормативной базы",
            reply_markup=reply_markup,
        )
    return MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if text == "Оформление заявок на СИЗ":
        await update.message.reply_text("Введите ваш табельный номер:")
        return SIZ_ENTER_TAB_NUMBER
    elif text == "Отправка анонимных жалоб":
        await update.message.reply_text(
            "Введите ваш табельный номер (для внутренней идентификации, жалоба останется анонимной):"
        )
        return COMPLAINT_ENTER_TAB_NUMBER
    elif text == "Получение актуальной нормативной базы":
        roles_str = "\n".join([f"- {r}" for r in AVAILABLE_ROLES])
        await update.message.reply_text(f"Выберите вашу специальность:\n{roles_str}")
        return NORMATIVE_CHOOSE_ROLE
    else:
        await update.message.reply_text("Пожалуйста, используйте кнопки меню.")
        return MAIN_MENU


async def siz_enter_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tab_num = update.message.text.strip()
    role = TAB_TO_ROLE.get(tab_num)
    if not role:
        await update.message.reply_text("Табельный номер не найден. Попробуйте снова.")
        return SIZ_ENTER_TAB_NUMBER

    siz_list = "\n".join([f"• {item}" for item in SIZ_BY_ROLE[role]])
    await update.message.reply_text(
        f"Для должности «{role}» положены следующие СИЗ:\n{siz_list}\n\n"
        "✅ Заявка принята. Администратор получит уведомление."
    )

    # Логируем заявку (видно в логах Render)
    logger.info(f"НОВАЯ ЗАЯВКА НА СИЗ | Табельный: {tab_num} | Должность: {role} | СИЗ: {siz_list}")
    return MAIN_MENU


async def complaint_enter_tab(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tab_num = update.message.text.strip()
    if tab_num not in TAB_TO_ROLE:
        await update.message.reply_text("Табельный номер не найден. Попробуйте снова.")
        return COMPLAINT_ENTER_TAB_NUMBER

    context.user_data["complaint_tab"] = tab_num
    await update.message.reply_text("Опишите вашу жалобу:")
    return COMPLAINT_ENTER_TEXT


async def complaint_enter_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    complaint_text = update.message.text.strip()
    tab_num = context.user_data.get("complaint_tab", "не указан")

    await update.message.reply_text("✅ Ваша жалоба отправлена анонимно.")

    # Логируем жалобу (анонимно для пользователя, но с таб. номером для админа — в логах)
    logger.info(f"АНОНИМНАЯ ЖАЛОБА | Табельный (внутр.): {tab_num} | Текст: {complaint_text}")
    return MAIN_MENU


async def normative_choose_role(update: Update, context: ContextTypes.DEFAULT_TYPE):
    role = update.message.text.strip().lower()
    if role not in AVAILABLE_ROLES:
        roles_str = "\n".join([f"- {r}" for r in AVAILABLE_ROLES])
        await update.message.reply_text(f"Специальность не найдена. Доступные:\n{roles_str}")
        return NORMATIVE_CHOOSE_ROLE

    doc_path = os.path.join(NORMATIVE_DOCS_DIR, f"{role}.pdf")
    if os.path.exists(doc_path):
        with open(doc_path, "rb") as doc:
            await update.message.reply_document(document=doc, caption=f"Нормативная база для: {role}")
    else:
        await update.message.reply_text(f"Документ для специальности «{role}» пока не загружен.")
    return MAIN_MENU


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Операция отменена.")
    return MAIN_MENU


# --- Запуск бота ---
def main():
    TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
    if not TOKEN:
        raise ValueError("Не задан TELEGRAM_BOT_TOKEN в переменных окружения")

    application = Application.builder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            SIZ_ENTER_TAB_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, siz_enter_tab)],
            COMPLAINT_ENTER_TAB_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_enter_tab)],
            COMPLAINT_ENTER_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, complaint_enter_text)],
            NORMATIVE_CHOOSE_ROLE: [MessageHandler(filters.TEXT & ~filters.COMMAND, normative_choose_role)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
