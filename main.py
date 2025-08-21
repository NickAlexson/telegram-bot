import os
from dotenv import load_dotenv

load_dotenv()

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
from datetime import datetime, time
import pytz
from flask import Flask
from threading import Thread

            # Читаем переменные из .env
BOT_TOKEN = os.getenv('BOT_TOKEN')
GROUP_CHAT_ID = int(os.getenv('GROUP_CHAT_ID', 0))
SPREADSHEET_ID_1 = os.getenv('SPREADSHEET_ID_1')
SPREADSHEET_ID_2 = os.getenv('SPREADSHEET_ID_2')

app = Flask('')

@app.route('/')
def home():
                return "Бот работает!"

def run():
                app.run(host='0.0.0.0', port=8080)

def keep_alive():
                t = Thread(target=run)
                t.start()

SCOPES = ['https://www.googleapis.com/auth/spreadsheets.readonly']

            # Авторизация Google Sheets
creds = Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
service = build('sheets', 'v4', credentials=creds)

            # Часовой пояс Москвы
MOSCOW_TZ = pytz.timezone('Europe/Moscow')

            # Список всех точек, которые должны быть в таблице
REQUIRED_POINTS = ['Титан Арена', 'Макси Арх', 'Макси Севск']

            # Универсальная функция для безопасной отправки сообщений
async def send(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str):
                if update and update.effective_message:
                    await update.effective_message.reply_text(text)
                elif update and update.effective_chat:
                    await context.bot.send_message(chat_id=update.effective_chat.id, text=text)
                else:
                    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)

            # Проверка, что на сегодняшнюю дату есть записи от всех точек
async def check_sheet(context: ContextTypes.DEFAULT_TYPE, spreadsheet_id, label: str):
                sheet = service.spreadsheets()
                result = sheet.values().get(spreadsheetId=spreadsheet_id, range='B:C').execute()
                values = result.get('values', [])

                today = datetime.now(MOSCOW_TZ).strftime('%d.%m.%Y')
                recorded_points = set()

                if not values:
                    msg = f'{label}: таблица пуста'
                    print(f"[{today}] {msg}")
                    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=msg)
                    return

                for row in values:
                    if len(row) < 2:
                        continue
                    date_value = row[0].strip()
                    point_value = row[1].strip()

                    if date_value == today:
                        recorded_points.add(point_value)

                missing_points = [point for point in REQUIRED_POINTS if point not in recorded_points]

                # Логирование в консоль
                print(f"[{today}] {label}")
                print(f"  ✅ Записались: {', '.join(recorded_points) if recorded_points else 'никто'}")
                print(f"  ❌ Отсутствуют: {', '.join(missing_points) if missing_points else 'нет'}")

                # Сообщения в Telegram
                if missing_points:
                    text = f'{label}: нет записи от {", ".join(missing_points)} на {today}'
                    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=text)
                else:
                    await context.bot.send_message(chat_id=GROUP_CHAT_ID, text=f'{label}: все точки сделали записи на {today}')

            # Ручная проверка по команде
async def manual_check(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await send(update, context, 'Запускаю проверку...')
                await check_sheet(context, SPREADSHEET_ID_1, 'Ручная проверка: Утренний Чек Лист')
                await check_sheet(context, SPREADSHEET_ID_2, 'Ручная проверка: Вечерний Чек Лист')

            # Обработчик команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await send(update, context, 'Бот запущен и готов к работе! Используй команду /check для ручной проверки.')

            # Обертки для задач расписания
async def check_morning(context: ContextTypes.DEFAULT_TYPE):
                await check_sheet(context, SPREADSHEET_ID_1, 'Утренняя проверка Чек листов')

async def check_evening(context: ContextTypes.DEFAULT_TYPE):
                await check_sheet(context, SPREADSHEET_ID_2, 'Вечерняя проверка Чек листов')

def main():
                app_tg = Application.builder().token(BOT_TOKEN).build()

                app_tg.add_handler(CommandHandler('start', start))
                app_tg.add_handler(CommandHandler('check', manual_check))

                # Утренняя проверка в 10:10 по Москве
                app_tg.job_queue.run_daily(
                    check_morning,
                    time=time(hour=10, minute=10, tzinfo=MOSCOW_TZ)
                )

                # Вечерняя проверка в 21:30 по Москве
                app_tg.job_queue.run_daily(
                    check_evening,
                    time=time(hour=21, minute=34, tzinfo=MOSCOW_TZ)
                )

                print('Бот запущен. Напишите /start для приветствия или /check для ручной проверки.')
                app_tg.run_polling()

if __name__ == '__main__':
                keep_alive()
                main()