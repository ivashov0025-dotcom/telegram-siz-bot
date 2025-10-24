import os
import logging
import sqlite3
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler

# Настройка Flask приложения
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Бот СИЗ работает! Токен: 8377876772:AAF5-fmyqvVyzCOVALSNiytd_MiJBcTbSow"

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Токен бота
TOKEN = "8377876772:AAF5-fmyqvVyzCOVALSNiytd_MiJBcTbSow"

# Состояния разговора
TABEL_NUMBER, MAIN_MENU, SIZ_SEASON, SIZ_SELECTION, VIOLATION_REPORT = range(5)
DB_NAME = "siz_bot.db"

def init_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        tabel_number TEXT UNIQUE,
        full_name TEXT,
        position TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS siz_orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        tabel_number TEXT,
        season TEXT,
        siz_item TEXT,
        quantity INTEGER,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS violations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reporter_tabel TEXT,
        violation_type TEXT,
        description TEXT,
        is_anonymous BOOLEAN DEFAULT 1,
        report_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    cursor.execute('''CREATE TABLE IF NOT EXISTS siz_catalog (
        position TEXT,
        season TEXT,
        siz_item TEXT,
        standard_quantity INTEGER
    )''')
    
    cursor.execute("SELECT COUNT(*) FROM siz_catalog")
    if cursor.fetchone()[0] == 0:
        siz_data = [
            ('Электрик', 'Летний', 'Каска защитная', 1),
            ('Электрик', 'Летний', 'Перчатки диэлектрические', 2),
            ('Электрик', 'Летний', 'Очки защитные', 1),
            ('Электрик', 'Зимний', 'Утепленная куртка', 1),
            ('Электрик', 'Зимний', 'Утепленные ботинки', 1),
        ]
        cursor.executemany("INSERT INTO siz_catalog VALUES (?, ?, ?, ?)", siz_data)
    
    conn.commit()
    conn.close()

def get_siz_items(season):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT siz_item, standard_quantity FROM siz_catalog WHERE season = ?", (season,))
    items = cursor.fetchall()
    conn.close()
    return items

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    await update.message.reply_text(f"Добро пожаловать, {user.first_name}!\n\nВведите ваш табельный номер:")
    return TABEL_NUMBER

async def handle_tabel_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tabel_number = update.message.text.strip()
    
    if len(tabel_number) < 2:
        await update.message.reply_text("Табельный номер слишком короткий. Попробуйте еще раз:")
        return TABEL_NUMBER
    
    user = update.effective_user
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO users (user_id, tabel_number, full_name, position) VALUES (?, ?, ?, ?)",
                  (user.id, tabel_number, f"{user.first_name}", "Электрик"))
    conn.commit()
    conn.close()
    
    context.user_data['tabel_number'] = tabel_number
    
    keyboard = [['🛡️ Заказать СИЗ'], ['🚨 Сообщить о нарушении'], ['📊 Статистика нарушений']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(f"Табельный номер {tabel_number} принят!\nВыберите действие:", reply_markup=reply_markup)
    return MAIN_MENU

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '🛡️ Заказать СИЗ':
        keyboard = [['Летний', 'Зимний'], ['↩️ Назад']]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите сезон СИЗ:", reply_markup=reply_markup)
        return SIZ_SEASON
        
    elif text == '🚨 Сообщить о нарушении':
        await update.message.reply_text("Опишите нарушение (анонимно):", reply_markup=ReplyKeyboardMarkup([['↩️ Отмена']], resize_keyboard=True))
        return VIOLATION_REPORT
        
    elif text == '📊 Статистика нарушений':
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM violations WHERE reporter_tabel = ?", (context.user_data['tabel_number'],))
        user_violations = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM violations")
        total_violations = cursor.fetchone()[0]
        conn.close()
        
        stats_text = f"📊 Статистика\n\nВсего нарушений: {total_violations}\nВами зафиксировано: {user_violations}"
        await update.message.reply_text(stats_text)
        return MAIN_MENU

async def siz_season(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '↩️ Назад':
        return await back_to_main(update, context)
    
    context.user_data['season'] = text
    siz_items = get_siz_items(text)
    
    keyboard = []
    for item, quantity in siz_items:
        keyboard.append([f"{item} ({quantity} шт)"])

    keyboard.append(['↩️ Назад'])
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"Выберите СИЗ для {text} сезона:", reply_markup=reply_markup)
    return SIZ_SELECTION

async def siz_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '↩️ Назад':
        return await back_to_main(update, context)
    
    siz_name = text.split(' (')[0]
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO siz_orders (user_id, tabel_number, season, siz_item, quantity) VALUES (?, ?, ?, ?, ?)",
                  (update.effective_user.id, context.user_data['tabel_number'], context.user_data['season'], siz_name, 1))
    conn.commit()
    conn.close()
    
    await update.message.reply_text(f"✅ Заказ оформлен: {siz_name} ({context.user_data['season']})")
    return await back_to_main(update, context)

async def violation_report(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    
    if text == '↩️ Отмена':
        return await back_to_main(update, context)
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO violations (reporter_tabel, violation_type, description) VALUES (?, ?, ?)",
                  (context.user_data['tabel_number'], "Сообщение от сотрудника", text))
    conn.commit()
    conn.close()
    
    await update.message.reply_text("✅ Нарушение отправлено анонимно!")
    return await back_to_main(update, context)

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [['🛡️ Заказать СИЗ'], ['🚨 Сообщить о нарушении'], ['📊 Статистика нарушений']]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Главное меню:", reply_markup=reply_markup)
    return MAIN_MENU

def run_bot():
    init_database()
    application = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TABEL_NUMBER: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_tabel_number)],
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            SIZ_SEASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, siz_season)],
            SIZ_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, siz_selection)],
            VIOLATION_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, violation_report)],
        },
        fallbacks=[]
    )
    
    application.add_handler(conv_handler)
    print("🤖 Бот СИЗ запущен!")
    application.run_polling()

if __name__ == '__main__':
    run_bot()
