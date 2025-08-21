import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, time
import pytz

# Загружаем переменные из .env
load_dotenv()
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))
SPREADSHEET_ID_1 = os.getenv('SPREADSHEET_ID_1')
SPREADSHEET_ID_2 = os.getenv('SPREADSHEET_ID_2')

# Google Sheets API
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# Временная зона
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Обязательные точки
REQUIRED_POINTS = ['Титан Арена', 'Макси Арх', 'Макси Севск']

# Проверка таблицы
async def check_sheet(context: ContextTypes.DEFAULT_TYPE, spreadsheet_id, label: str):
    sheet = service.spreadsheets()
    result = sheet.values().get(spreadsheetId=spreadsheet_id, range='B:C').execute()
    values = result.get('values', [])

    today = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
    recorded_points = set()

    for row in values:
        if len(row) < 2:
            continue
        date_value = row[0].strip()
        point_value = row[1].strip()
        if date_value == today:
            recorded_points.add(point_value)

    missing_points = [point for point in REQUIRED_POINTS if point not in recorded_points]

    if missing_points:
        text = f'{label}: нет записи от {", ".join(missing_points)} на {today}'
    else:
        text = f'{label}: все точки сделали записи на {today}'

    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)

# Команды
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Бот запущен ✅ Используй /check для ручной проверки.')

async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Запускаю проверку...')
    await check_sheet(context, SPREADSHEET_ID_1, 'Ручная проверка: Утренний Чек Лист')
    await check_sheet(context, SPREADSHEET_ID_2, 'Ручная проверка: Вечерний Чек Лист')

# Плановые задачи
async def morning_check(context: ContextTypes.DEFAULT_TYPE):
    await check_sheet(context, SPREADSHEET_ID_1, 'Утренняя проверка Чек листов')

async def evening_check(context: ContextTypes.DEFAULT_TYPE):
    await check_sheet(context, SPREADSHEET_ID_2, 'Вечерняя проверка Чек листов')

# Главная функция
def main():
    app_tg = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    app_tg.add_handler(CommandHandler('start', start))
    app_tg.add_handler(CommandHandler('check', manual_check))

    # Расписание
    job_queue = app_tg.job_queue
    job_queue.run_daily(
        morning_check,
        time=time(hour=10, minute=10, tzinfo=MOSCOW_TZ)
    )
    job_queue.run_daily(
        evening_check,
        time=time(hour=21, minute=30, tzinfo=MOSCOW_TZ)
    )

    print('Бот запущен ✅ Ожидает команды...')
    app_tg.run_polling()

if __name__ == '__main__':
    main()