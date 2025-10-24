import logging
import sqlite3
from datetime import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, 
    ContextTypes, ConversationHandler
)

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# Состояния разговора
TABEL_NUMBER, MAIN_MENU, SIZ_SEASON, SIZ_SELECTION, VIOLATION_REPORT = range(5)

# База данных
DB_NAME = "siz_bot.db"

# Инициализация базы данных
def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Таблица пользователей
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            tabel_number TEXT UNIQUE,
            full_name TEXT,
            position TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Таблица заказов СИЗ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS siz_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tabel_number TEXT,
            season TEXT,
            siz_item TEXT,
            quantity INTEGER,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (user_id)
        )
    ''')
    
    # Таблица нарушений
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reporter_tabel TEXT,
            violation_type TEXT,
            description TEXT,
            location TEXT,
            is_anonymous BOOLEAN DEFAULT 1,
            report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Справочник СИЗ по должностям
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS siz_catalog (
            position TEXT,
            season TEXT,
            siz_item TEXT,
            standard_quantity INTEGER
        )
    ''')
    
    # Заполняем справочник СИЗ (примерные данные)
    siz_data = [
        ('Электрик', 'летний', 'Каска защитная', 1),
        ('Электрик', 'летний', 'Перчатки диэлектрические', 2),
        ('Электрик', 'летний', 'Очки защитные', 1),
        ('Электрик', 'зимний', 'Утепленная курка', 1),
        ('Электрик', 'зимний', 'Утепленные ботинки', 1),
        ('Сварщик', 'летний', 'Маска сварщика', 1),
        ('Сварщик', 'летний', 'Краги', 2),
        ('Сварщик', 'летний', 'Спецкостюм', 1),
        ('Сварщик', 'зимний', 'Утепленный спецкостюм', 1),
        ('Сварщик', 'зимний', 'Утепленные перчатки', 2),
        ('Слесарь', 'летний', 'Комбинезон', 1),
        ('Слесарь', 'летний', 'Перчатки', 4),
        ('Слесарь', 'зимний', 'Утепленный комбинезон', 1),
        ('Слесарь', 'зимний', 'Утепленные перчатки', 4)
    ]
    
    cursor.execute("SELECT COUNT(*) FROM siz_catalog")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO siz_catalog (position, season, siz_item, standard_quantity) VALUES (?, ?, ?, ?)",
            siz_data
        )
    
    conn.commit()
    conn.close()

# Получение СИЗ для должности
def get_siz_for_position(position, season):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT siz_item, standard_quantity FROM siz_catalog WHERE position = ? AND season = ?",
        (position, season)
    )
    
    result = cursor.fetchall()
    conn.close()
    return result

# Сохранение пользователя
def save_user(user_id, tabel_number, full_name, position):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (user_id, tabel_number, full_name, position)
        VALUES (?, ?, ?, ?)
    ''', (user_id, tabel_number, full_name, position))
    
    conn.commit()
    conn.close()

# Получение пользователя по табельному номеру
def get_user_by_tabel(tabel_number):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM users WHERE tabel_number = ?", (tabel_number,))
    result = cursor.fetchone()
    conn.close()
    
    return result

# Сохранение заказа СИЗ
def save_siz_order(user_id, tabel_number, season, siz_item, quantity):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO siz_orders (user_id, tabel_number, season, siz_item, quantity)
        VALUES (?, ?, ?, ?, ?)
    ''', (user_id, tabel_number, season, siz_item, quantity))
    
    conn.commit()
    conn.close()

# Сохранение нарушения
def save_violation(reporter_tabel, violation_type, description, location, is_anonymous=True):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO violations (reporter_tabel, violation_type, description, location, is_anonymous)
        VALUES (?, ?, ?, ?, ?)
    ''', (reporter_tabel, violation_type, description, location, is_anonymous))
    
    conn.commit()
    conn.close()

# Получение статистики нарушений
def get_violation_stats(tabel_number):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Нарушения, зафиксированные на этого сотрудника
    cursor.execute('''
        SELECT violation_type, COUNT(*) as count 
        FROM violations 
        WHERE reporter_tabel = ? 
        GROUP BY violation_type
    ''', (tabel_number,))
    
    reported_violations = cursor.fetchall()
    
    # Всего нарушений в системе
    cursor.execute("SELECT COUNT(*) FROM violations")
    total_violations = cursor.fetchone()[0]
    
    conn.close()
    
    return reported_violations, total_violations

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    await update.message.reply_text(
        f"Добро пожаловать, {user.first_name}!\n\n"
        "Для начала работы введите ваш табельный номер:",
        reply_markup=ReplyKeyboardRemove()
    )
    
    return TABEL_NUMBER

# Обработка табельного номера
async def handle_tabel_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tabel_number = update.message.text.strip()
    
    # Здесь должна быть проверка табельного номера в вашей системе
    # Для примера - простая имитация
    if len(tabel_number) < 3:
        await update.message.reply_text("Табельный номер слишком короткий. Попробуйте еще раз:")
        return TABEL_NUMBER
    
    # Сохраняем пользователя (в реальной системе здесь бы проверка в базе сотрудников)
    user = update.effective_user
    save_user(user.id, tabel_number, f"{user.first_name} {user.last_name or ''}", "Электрик")
    
    context.user_data['tabel_number'] = tabel_number
    
    # Показываем главное меню
    keyboard = [
        ['🛡️ Заказать СИЗ'],
        ['🚨 Сообщить о нарушении анонимно'],
        ['📊 Статистика нарушений']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Табельный номер {tabel_number} принят!\n"
        "Выберите действие:",
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

# Главное меню
async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    tabel_number = context.user_data.get('tabel_number')
    
    if text == '🛡️ Заказать СИЗ':
        keyboard = [['Летний СИЗ', 'Зимний СИЗ'], ['↩️ Назад']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Выберите сезон СИЗ:",
            reply_markup=reply_markup
        )
        return SIZ_SEASON
        
    elif text == '🚨 Сообщить о нарушении анонимно':
        await update.message.reply_text(
            "Опишите нарушение, которое вы обнаружили:\n\n"
            "Укажите:\n"
            "• Тип нарушения\n"
            "• Местоположение\n"
            "• Подробное описание\n\n"
            "Ваше сообщение будет отправлено анонимно.",
            reply_markup=ReplyKeyboardMarkup([['↩️ Отмена']], resize_keyboard=True)
        )
        return VIOLATION_REPORT
        
    elif text == '📊 Статистика нарушений':
        reported_violations, total_violations = get_violation_stats(tabel_number)
        
        stats_text = f"📊 Статистика нарушений\n\n"
        stats_text += f"Всего нарушений в системе: {total_violations}\n\n"
        
        if reported_violations:
            stats_text += "Вами зафиксировано:\n"
            for violation_type, count in reported_violations:
                stats_text += f"• {violation_type}: {count}\n"
        else:
            stats_text += "Вы еще не фиксировали нарушений"
        
        await update.message.reply_text(stats_text)
        return MAIN_MENU

# Выбор сезона СИЗ
async def siz_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '↩️ Назад':
        return await back_to_main(update, context)
    
    season = "летний" if "Летний" in text else "зимний"
    context.user_data['selected_season'] = season
    
    # Получаем СИЗ для должности пользователя
    user_position = "Электрик"  # В реальной системе брать из базы
    siz_items = get_siz_for_position(user_position, season)
    
    if not siz_items:
        await update.message.reply_text("Для вашей должности СИЗ не найдены")
        return await back_to_main(update, context)
    
    # Сохраняем список СИЗ в контексте
    context.user_data['siz_items'] = siz_items
    
    # Создаем клавиатуру с СИЗ
    keyboard = []
    for item, quantity in siz_items:
        keyboard.append([f"{item} (норма: {quantity} шт.)"])
    keyboard.append(['↩️ Назад'])
    
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        f"Выберите СИЗ для {season} сезона:\n"
        "Нажмите на нужную позицию для заказа:",
        reply_markup=reply_markup
    )
    
    return SIZ_SELECTION

# Выбор СИЗ для заказа
async def siz_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '↩️ Назад':
        return await back_to_main(update, context)
    
    # Извлекаем название СИЗ из текста кнопки
    siz_name = text.split(' (норма:')[0]
    season = context.user_data.get('selected_season')
    tabel_number = context.user_data.get('tabel_number')
    
    # Находим стандартное количество
    siz_items = context.user_data.get('siz_items', [])
    quantity = 1
    for item, std_quantity in siz_items:
        if item == siz_name:
            quantity = std_quantity
            break
    
    # Сохраняем заказ
    save_siz_order(update.effective_user.id, tabel_number, season, siz_name, quantity)
    
    await update.message.reply_text(
        f"✅ Заказ оформлен!\n\n"
        f"СИЗ: {siz_name}\n"
        f"Сезон: {season}\n"
        f"Количество: {quantity} шт.\n"
        f"Табельный: {tabel_number}\n\n"
        f"Заказ передан в отдел снабжения.",
        reply_markup=ReplyKeyboardMarkup([['🛡️ Заказать СИЗ', '📊 Статистика'], ['↩️ Главное меню']], resize_keyboard=True)
    )
    
    return MAIN_MENU

# Сообщение о нарушении
async def violation_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '↩️ Отмена':
        return await back_to_main(update, context)
    
    violation_description = text
    tabel_number = context.user_data.get('tabel_number')
    
    # Сохраняем нарушение (анонимно)
    save_violation(
        reporter_tabel=tabel_number,
        violation_type="Сообщение от сотрудника",
        description=violation_description,
        location="Не указано",
        is_anonymous=True
    )
    
    await update.message.reply_text(
        "✅ Сообщение о нарушении отправлено анонимно!\n"
        "Спасибо за вашу бдительность.",
        reply_markup=ReplyKeyboardMarkup([
            ['🚨 Сообщить о нарушении', '📊 Статистика'],
            ['↩️ Главное меню']
        ], resize_keyboard=True)
    )
    
    return MAIN_MENU

# Возврат в главное меню
async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ['🛡️ Заказать СИЗ'],
        ['🚨 Сообщить о нарушении анонимно'],
        ['📊 Статистика нарушений']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Главное меню:",
        reply_markup=reply_markup
    )
    
    return MAIN_MENU

# Отмена разговора
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Диалог прерван. Используйте /start для начала работы.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main():
    # Инициализация базы данных
    init_database()
    
    # Создание приложения
    application = Application.builder().token("8377876772:AAF5-fmyqvVyzCOVALSNiytd_MiJBcTbSow").build()
    
    # Обработчик разговора
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TABEL_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tabel_number)
            ],
            MAIN_MENU: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)
            ],
            SIZ_SEASON: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, siz_season)
            ],
            SIZ_SELECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, siz_selection)
            ],
            VIOLATION_REPORT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, violation_report)
            ],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    
    application.add_handler(conv_handler)
    
    # Запуск бота
    print("Бот СИЗ запущен...")
    application.run_polling()

if __name__ == '__main__':
    main()