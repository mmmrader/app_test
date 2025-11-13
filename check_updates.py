import os
import re
import json
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import logging

# --- Налаштування ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHANNEL_USERNAME = 'SvitloOleksandriyskohoRaionu' 
SCAN_LIMIT = 10 # <-- ‼️ ОНОВЛЕННЯ: Перевіряємо 10, а не 1

ARCHIVE_DIR = "archive"
LATEST_FILE = "latest.json"
INDEX_FILE = "index.json"

# --- Завантаження Секретів з GitHub Actions ---
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('TELETHON_SESSION')
# -----------------

# --- (Функції parse_schedule_message, read_json_file, write_json_file - БЕЗ ЗМІН) ---

def parse_schedule_message(text):
    change_time_match = re.search(r'Зміни на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})', text)
    change_time = change_time_match.group(1) if change_time_match else None
    schedule_date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4}) внесено зміни', text)
    if not schedule_date_match: return None, None
    day, month, year = schedule_date_match.groups()
    schedule_date_iso = f"{year}-{month}-{day}"
    queue_matches = re.findall(r'(Черга [\d\.]+): (.*)', text)
    queues = []
    for match in queue_matches:
        queue_name = match[0].replace('Черга ', '').strip()
        times = [t.strip() for t in match[1].split(',')]
        queues.append({"queue_name": queue_name, "times": times})
    if not queues: return None, None
    return {
        "change_timestamp_str": change_time,
        "schedule_date_str": f"{day}.{month}.{year}",
        "queues": queues
    }, schedule_date_iso

def read_json_file(path, default_data):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_data

def write_json_file(path, data):
    dir_name = os.path.dirname(path)
    if dir_name: 
        os.makedirs(dir_name, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- ‼️ ОНОВЛЕНА ФУНКЦІЯ main() ‼️ ---
def main():
    log.info(f"[{datetime.datetime.now()}] Запуск перевірки оновлень...")
    
    if not all([API_ID, API_HASH, SESSION_STRING]):
        log.error("Критичні секрети (API_ID, API_HASH, SESSION) не встановлені. Роботу зупинено.")
        return

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    with client:
        log.info(f"Підключення до Telegram... Читання каналу: {CHANNEL_USERNAME}")
        
        new_data = None
        schedule_date = None
        
        try:
            # Отримуємо 10 останніх повідомлень
            messages = client.get_messages(CHANNEL_USERNAME, limit=SCAN_LIMIT)
        except Exception as e:
            log.error(f"Помилка отримання повідомлень з каналу: {e}")
            return
            
        # Шукаємо з найновішого до найстарішого
        for msg in messages:
            if not msg.text:
                continue
                
            # Намагаємось розпарсити
            new_data, schedule_date = parse_schedule_message(msg.text)
            
            if new_data:
                # Успіх! Ми знайшли найновіший валідний графік.
                log.info(f"Знайдено останній валідний графік (від {new_data.get('change_timestamp_str')})")
                break # Зупиняємо цикл

        # --- Кінець нового блоку ---

        if not new_data:
            log.info(f"Не знайдено валідних графіків в останніх {SCAN_LIMIT} повідомленнях. Пропуск.")
            return

        log.info(f"Обробка графіка від {new_data['change_timestamp_str']} на дату {schedule_date}")

        # --- Головна логіка: Порівняння (Без змін) ---
        old_latest = read_json_file(LATEST_FILE, {})
        
        if old_latest.get('change_timestamp_str') == new_data.get('change_timestamp_str'):
            log.info("Це той самий графік, що і минулого разу. Оновлення не потрібне.")
            return

        log.info("!!! Виявлено НОВИЙ графік! Оновлюємо файли...")

        write_json_file(LATEST_FILE, new_data)
        log.info(f"Файл {LATEST_FILE} оновлено.")

        archive_path = os.path.join(ARCHIVE_DIR, f"{schedule_date}.json")
        write_json_file(archive_path, new_data)
        log.info(f"Файл архіву {archive_path} оновлено.")

        index_data = read_json_file(INDEX_FILE, {"available_dates": []})
        if schedule_date not in index_data["available_dates"]:
            index_data["available_dates"].append(schedule_date)
            index_data["available_dates"].sort(reverse=True) 
            write_json_file(INDEX_FILE, index_data)
            log.info(f"Файл {INDEX_FILE} оновлено, додано дату {schedule_date}.")
        else:
            log.info(f"Дата {schedule_date} вже є в індексі.")

if __name__ == "__main__":
    main()