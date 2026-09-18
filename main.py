import os

from dotenv import load_dotenv

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials

from datetime import datetime, time, timedelta

import pytz


# ============================================================
# ENV
# ============================================================

load_dotenv()

# -------------------- Основной чат --------------------

BOT_TOKEN = os.getenv('BOT_TOKEN')

GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID'))

TOPIC_ID = os.getenv('TOPIC_ID')
if TOPIC_ID:
    TOPIC_ID = int(TOPIC_ID)

# Таблицы Титан Арена + Макси Севск
SPREADSHEET_ID_1 = os.getenv('SPREADSHEET_ID_1')  # утро
SPREADSHEET_ID_2 = os.getenv('SPREADSHEET_ID_2')  # вечер


# -------------------- Мурманск --------------------

# Пока значения могут отсутствовать.
# Они понадобятся после получения ID второго чата и таблиц.

GROUP_CHAT_ID_M_VALUE = os.getenv('GROUP_CHAT_ID_M')

if GROUP_CHAT_ID_M_VALUE:
    GROUP_CHAT_ID_M = int(GROUP_CHAT_ID_M_VALUE)
else:
    GROUP_CHAT_ID_M = None


TOPIC_ID_M = os.getenv('TOPIC_ID_M')

if TOPIC_ID_M:
    TOPIC_ID_M = int(TOPIC_ID_M)


SPREADSHEET_ID_M_1 = os.getenv('SPREADSHEET_ID_M_1')  # утро
SPREADSHEET_ID_M_2 = os.getenv('SPREADSHEET_ID_M_2')  # вечер


# -------------------- Проверка BOT_TOKEN --------------------

if not BOT_TOKEN:
    raise ValueError('BOT_TOKEN не найден в .env')


# ============================================================
# GOOGLE SHEETS
# ============================================================

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets.readonly'
]

creds = Credentials.from_service_account_file(
    'credentials.json',
    scopes=SCOPES
)

service = build(
    'sheets',
    'v4',
    credentials=creds
)


# ============================================================
# SETTINGS
# ============================================================

MOSCOW_TZ = pytz.timezone('Europe/Moscow')

# Основные точки
REQUIRED_POINTS = [
    'Титан Арена',
    'Макси Севск'
]

# Мурманские точки
REQUIRED_POINTS_M = [
    'Мурманск Молл',
    'Плазма',
    'Северное Нагорное'
]

CHECK_RANGE = 'B:C'

DAYS_FOR_SVOD = 14


# ============================================================
# SEND MESSAGE
# ============================================================

async def send_message(
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
    chat_id: int,
    topic_id=None
):
    """
    Отправляет сообщение в указанный чат.
    Если указан topic_id — сообщение отправляется в тему форума.
    """

    if topic_id:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text,
            message_thread_id=topic_id
        )
    else:
        await context.bot.send_message(
            chat_id=chat_id,
            text=text
        )


# ============================================================
# CHECK TODAY
# ============================================================

async def check_sheet(
    context: ContextTypes.DEFAULT_TYPE,
    spreadsheet_id: str,
    label: str,
    required_points: list,
    chat_id: int,
    topic_id=None
):
    """
    Проверяет сегодняшние записи в Google Таблице.

    B = дата
    C = название точки
    """

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
        point
        for point in required_points
        if point not in recorded_points
    ]

    if missing_points:

        text = (
            f'{label}: ❌ нет записи от '
            f'{", ".join(missing_points)} на {today}'
        )

    else:

        text = (
            f'{label}: ✅ все точки сделали записи на {today}'
        )

    await send_message(
        context,
        text,
        chat_id,
        topic_id
    )


# ============================================================
# SVOD HELPERS
# ============================================================

def get_records_for_period(
    spreadsheet_id: str,
    days: int
):
    """
    Получает записи из Google Таблицы за указанный период.
    """

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
            row_date = datetime.strptime(
                row[0].strip(),
                '%d.%m.%Y'
            ).date()

        except ValueError:
            continue

        if not (start_date <= row_date <= today):
            continue

        date_key = row_date.strftime('%d.%m.%Y')

        point = row[1].strip()

        data.setdefault(date_key, set()).add(point)

    return data


# ============================================================
# BUILD SVOD
# ============================================================

def build_svod(
    spreadsheet_id_morning: str,
    spreadsheet_id_evening: str,
    required_points: list,
    days: int
):
    """
    Формирует сводку для конкретной группы точек.
    """

    morning = get_records_for_period(
        spreadsheet_id_morning,
        days
    )

    evening = get_records_for_period(
        spreadsheet_id_evening,
        days
    )

    today = datetime.now(MOSCOW_TZ).date()

    start_date = today - timedelta(days=days)

    result = []

    current_date = start_date

    while current_date <= today:

        date_key = current_date.strftime('%d.%m.%Y')

        missing = []

        for point in required_points:

            if point not in morning.get(date_key, set()):
                missing.append(
                    f'❌ {point} — утро'
                )

            if point not in evening.get(date_key, set()):
                missing.append(
                    f'❌ {point} — вечер'
                )

        if not missing:

            result.append(
                f'{date_key[:5]} ✅ все точки'
            )

        else:

            result.append(
                f'{date_key[:5]}'
            )

            result.extend(missing)

        result.append('')

        current_date += timedelta(days=1)

    return '\n'.join(result).strip()


# ============================================================
# COMMAND: /START
# ============================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        'Бот запущен ✅\n'
        '\n'
        'Основные команды:\n'
        '/check — ручная проверка\n'
        '/svod — сводка за 14 дней\n'
        '\n'
        'Мурманск:\n'
        '/checkm — ручная проверка\n'
        '/svodm — сводка за 14 дней\n'
        '\n'
        '/id — узнать ID чата и темы'
    )


# ============================================================
# COMMAND: /ID
# ============================================================

async def chat_id(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    """
    Показывает ID текущего чата и темы.
    """

    chat_id_value = update.effective_chat.id

    thread_id = None

    if update.message:
        thread_id = update.message.message_thread_id

    await update.message.reply_text(
        f'Chat ID: {chat_id_value}\n'
        f'Topic ID: {thread_id}'
    )


# ============================================================
# COMMAND: /CHECK
# ============================================================

async def manual_check(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        'Запускаю проверку...'
    )

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_1,
        label='Ручная проверка: Утренний чек-лист',
        required_points=REQUIRED_POINTS,
        chat_id=GROUP_CHAT_ID,
        topic_id=TOPIC_ID
    )

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_2,
        label='Ручная проверка: Вечерний чек-лист',
        required_points=REQUIRED_POINTS,
        chat_id=GROUP_CHAT_ID,
        topic_id=TOPIC_ID
    )


# ============================================================
# COMMAND: /SVOD
# ============================================================

async def svod(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        'Формирую сводку за 14 дней ⏳'
    )

    try:

        text = build_svod(
            spreadsheet_id_morning=SPREADSHEET_ID_1,
            spreadsheet_id_evening=SPREADSHEET_ID_2,
            required_points=REQUIRED_POINTS,
            days=DAYS_FOR_SVOD
        )

    except Exception as e:

        await update.message.reply_text(
            f'Ошибка формирования сводки ❌\n{e}'
        )

        return

    if not text:
        text = 'Нет данных за указанный период'

    await update.message.reply_text(text)


# ============================================================
# COMMAND: /CHECKM
# ============================================================

async def manual_check_m(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not GROUP_CHAT_ID_M:
        await update.message.reply_text(
            'Мурманск пока не настроен ❌\n'
            'Сначала добавьте GROUP_CHAT_ID_M в .env'
        )
        return

    if not SPREADSHEET_ID_M_1 or not SPREADSHEET_ID_M_2:
        await update.message.reply_text(
            'Не указаны таблицы Мурманска ❌'
        )
        return

    await update.message.reply_text(
        'Запускаю проверку Мурманска...'
    )

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_M_1,
        label='Ручная проверка: Утренний чек-лист Мурманск',
        required_points=REQUIRED_POINTS_M,
        chat_id=GROUP_CHAT_ID_M,
        topic_id=TOPIC_ID_M
    )

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_M_2,
        label='Ручная проверка: Вечерний чек-лист Мурманск',
        required_points=REQUIRED_POINTS_M,
        chat_id=GROUP_CHAT_ID_M,
        topic_id=TOPIC_ID_M
    )


# ============================================================
# COMMAND: /SVODM
# ============================================================

async def svod_m(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    if not SPREADSHEET_ID_M_1 or not SPREADSHEET_ID_M_2:
        await update.message.reply_text(
            'Таблицы Мурманска пока не настроены ❌'
        )
        return

    await update.message.reply_text(
        'Формирую сводку Мурманска за 14 дней ⏳'
    )

    try:

        text = build_svod(
            spreadsheet_id_morning=SPREADSHEET_ID_M_1,
            spreadsheet_id_evening=SPREADSHEET_ID_M_2,
            required_points=REQUIRED_POINTS_M,
            days=DAYS_FOR_SVOD
        )

    except Exception as e:

        await update.message.reply_text(
            f'Ошибка формирования сводки Мурманска ❌\n{e}'
        )

        return

    if not text:
        text = 'Нет данных за указанный период'

    MAX_MESSAGE_LENGTH=4000

    for i in range(0, len(text), MAX_MESSAGE_LENGTH):
        await update.message.reply_text(text[i:i + MAX_MESSAGE_LENGTH)


# ============================================================
# SCHEDULE — ОСНОВНЫЕ ТОЧКИ
# ============================================================

async def morning_check(
    context: ContextTypes.DEFAULT_TYPE
):

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_1,
        label='Утренняя проверка чек-листов',
        required_points=REQUIRED_POINTS,
        chat_id=GROUP_CHAT_ID,
        topic_id=TOPIC_ID
    )


async def evening_check(
    context: ContextTypes.DEFAULT_TYPE
):

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_2,
        label='Вечерняя проверка чек-листов',
        required_points=REQUIRED_POINTS,
        chat_id=GROUP_CHAT_ID,
        topic_id=TOPIC_ID
    )


# ============================================================
# SCHEDULE — МУРМАНСК
# ============================================================

async def morning_check_m(
    context: ContextTypes.DEFAULT_TYPE
):

    if not GROUP_CHAT_ID_M:
        return

    if not SPREADSHEET_ID_M_1:
        return

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_M_1,
        label='Утренняя проверка чек-листов Мурманск',
        required_points=REQUIRED_POINTS_M,
        chat_id=GROUP_CHAT_ID_M,
        topic_id=TOPIC_ID_M
    )


async def evening_check_m(
    context: ContextTypes.DEFAULT_TYPE
):

    if not GROUP_CHAT_ID_M:
        return

    if not SPREADSHEET_ID_M_2:
        return

    await check_sheet(
        context=context,
        spreadsheet_id=SPREADSHEET_ID_M_2,
        label='Вечерняя проверка чек-листов Мурманск',
        required_points=REQUIRED_POINTS_M,
        chat_id=GROUP_CHAT_ID_M,
        topic_id=TOPIC_ID_M
    )


# ============================================================
# MAIN
# ============================================================

def main():

    app_tg = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )

    # -------------------- Команды --------------------

    app_tg.add_handler(
        CommandHandler('start', start)
    )

    app_tg.add_handler(
        CommandHandler('id', chat_id)
    )

    app_tg.add_handler(
        CommandHandler('check', manual_check)
    )

    app_tg.add_handler(
        CommandHandler('svod', svod)
    )

    app_tg.add_handler(
        CommandHandler('checkm', manual_check_m)
    )

    app_tg.add_handler(
        CommandHandler('svodm', svod_m)
    )

    # -------------------- Планировщик --------------------

    job_queue = app_tg.job_queue

    # Основные точки — утро
    job_queue.run_daily(
        morning_check,
        time=time(
            hour=10,
            minute=10,
            tzinfo=MOSCOW_TZ
        )
    )

    # Основные точки — вечер
    job_queue.run_daily(
        evening_check,
        time=time(
            hour=21,
            minute=30,
            tzinfo=MOSCOW_TZ
        )
    )

    # Мурманск — утро
    job_queue.run_daily(
        morning_check_m,
        time=time(
            hour=10,
            minute=10,
            tzinfo=MOSCOW_TZ
        )
    )

    # Мурманск — вечер
    job_queue.run_daily(
        evening_check_m,
        time=time(
            hour=21,
            minute=30,
            tzinfo=MOSCOW_TZ
        )
    )

    print(
        'Бот запущен ✅ '
        'Ожидает команды...'
    )

    app_tg.run_polling()


# ============================================================
# START
# ============================================================

if __name__ == '__main__':
    main()
