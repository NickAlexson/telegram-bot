import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, time, timedelta
import pytz

# ================== ENV ==================
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))

TOPIC_ID = os.getenv('TOPIC_ID')
if TOPIC_ID:
    TOPIC_ID = int(TOPIC_ID)

SPREADSHEET_ID_1 = os.getenv('SPREADSHEET_ID_1')  # утро
SPREADSHEET_ID_2 = os.getenv('SPREADSHEET_ID_2')  # вечер

if not BOT_TOKEN:
    raise ValueError('BOT_TOKEN не найден в .env')

# ================== GOOGLE SHEETS ==================
SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

# ================== SETTINGS ==================
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

REQUIRED_POINTS = [
    'Титан Арена',
    'Макси Севск'
]

CHECK_RANGE = 'B:C'
DAYS_FOR_SVOD = 14

# ================== HELPERS ==================
async def send_message(context: ContextTypes.DEFAULT_TYPE, text: str):
    if TOPIC_ID:
        await context.bot.send_message(
            chat_id=GROUP_CHAT_ID,
            text=text,
            message_thread_id=TOPIC_ID
        )
    else:
        await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)


# ================== CHECK TODAY ==================
async def check_sheet(context: ContextTypes.DEFAULT_TYPE, spreadsheet_id, label: str):
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range=CHECK_RANGE
    ).execute()

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

    missing_points = [
        point for point in REQUIRED_POINTS
        if point not in recorded_points
    ]

    if missing_points:
        text = f'{label}: ❌ нет записи от {", ".join(missing_points)} на {today}'
    else:
        text = f'{label}: ✅ все точки сделали записи на {today}'

    await send_message(context, text)


# ================== SVOD HELPERS ==================
def get_records_for_period(spreadsheet_id, days: int):
    sheet = service.spreadsheets()
    result = sheet.values().get(
        spreadsheetId=spreadsheet_id,
        range=CHECK_RANGE
    ).execute()

    values = result.get('values', [])
    today = datetime.now(MOSCOW_TZ).date()
    start_date = today - timedelta(days=days)

    data = {}

    for row in values:
        if len(row) < 2:
            continue

        try:
            row_date = datetime.strptime(row[0].strip(), '%d.%m.%Y').date()
        except ValueError:
            continue

        if not (start_date <= row_date <= today):
            continue

        date_key = row_date.strftime('%d.%m.%Y')
        point = row[1].strip()

        data.setdefault(date_key, set()).add(point)

    return data


def build_svod(days: int):
    morning = get_records_for_period(SPREADSHEET_ID_1, days)
    evening = get_records_for_period(SPREADSHEET_ID_2, days)

    all_dates = sorted(set(morning) | set(evening))
    result = []

    for date in all_dates:
        missing = []

        for point in REQUIRED_POINTS:
            if point not in morning.get(date, set()):
                missing.append(f'❌ {point} — утро')
            if point not in evening.get(date, set()):
                missing.append(f'❌ {point} — вечер')

        if not missing:
            result.append(f'{date[:5]} ✅ все точки')
        else:
            result.append(f'{date[:5]}')
            result.extend(missing)

        result.append('')

    return '\n'.join(result).strip()
# ================== COMMANDS ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        'Бот запущен ✅\n'
        'Команды:\n'
        '/check — ручная проверка\n'
        '/svod — сводка за 14 дней'
    )


async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Запускаю проверку...')
    await check_sheet(context, SPREADSHEET_ID_1, 'Ручная проверка: Утренний чек-лист')
    await check_sheet(context, SPREADSHEET_ID_2, 'Ручная проверка: Вечерний чек-лист')


async def svod(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Формирую сводку за 14 дней ⏳')

    try:
        text = build_svod(DAYS_FOR_SVOD)
    except Exception as e:
        await update.message.reply_text(f'Ошибка формирования сводки ❌\n{e}')
        return

    if not text:
        text = 'Нет данных за указанный период'

    await update.message.reply_text(text)


# ================== SCHEDULE ==================
async def morning_check(context: ContextTypes.DEFAULT_TYPE):
    await check_sheet(context, SPREADSHEET_ID_1, 'Утренняя проверка чек-листов')


async def evening_check(context: ContextTypes.DEFAULT_TYPE):
    await check_sheet(context, SPREADSHEET_ID_2, 'Вечерняя проверка чек-листов')


# ================== MAIN ==================
def main():
    app_tg = ApplicationBuilder().token(BOT_TOKEN).build()

    # Команды
    app_tg.add_handler(CommandHandler('start', start))
    app_tg.add_handler(CommandHandler('check', manual_check))
    app_tg.add_handler(CommandHandler('svod', svod))

    # Планировщик
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
