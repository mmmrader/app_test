import os
import re
import json
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import logging

# --- Настройки ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

CHANNEL_USERNAME = 'SvitloOleksandriyskohoRaionu' 
SCAN_LIMIT = 10 # Проверяем 10 последних

ARCHIVE_DIR = "archive"
LATEST_FILE = "latest.json"
INDEX_FILE = "index.json"

# --- Загрузка Секретов ---
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('TELETHON_SESSION')
# -----------------

# --- ‼️ НОВАЯ ВЕРСИЯ ПАРСЕРА ‼️ ---
def parse_schedule_message(text):
    """
    Универсальный парсер, который понимает 
    "внесено зміни" И "буде діяти".
    """
    
    # 1. Ищем дату графика (любым из двух способов)
    # "За розпорядженням НЕК "Укренерго" 14.11.2025 буде діяти"
    # "За розпорядженням НЕК "Укренерго" 12.11.2025 внесено зміни"
    date_pattern = r"За розпорядженням НЕК \"Укренерго\" (\d{2})\.(\d{2})\.(\d{4}) (?:буде діяти|внесено зміни)"
    schedule_date_match = re.search(date_pattern, text)
    
    if not schedule_date_match:
        # Это не сообщение с графиком
        return None, None

    day, month, year = schedule_date_match.groups()
    schedule_date_str = f"{day}.{month}.{year}" # "14.11.2025"
    schedule_date_iso = f"{year}-{month}-{day}" # "2025-11-14"

    # 2. Ищем ВРЕМЯ обновления (оно опционально)
    # "⚡ Зміни на 21:31 12.11.2025 до графіка"
    change_time_match = re.search(r'Зміни на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})', text)
    change_time = change_time_match.group(1) if change_time_match else None

    # 3. Ищем очереди (без изменений)
    queue_matches = re.findall(r'(Черга [\d\.]+): (.*)', text)
    queues = []
    for match in queue_matches:
        queue_name = match[0].replace('Черга ', '').strip()
        times = [t.strip() for t in match[1].split(',')]
        queues.append({"queue_name": queue_name, "times": times})
        
    if not queues:
        # Нашли дату, но не нашли очередей
        return None, None
        
    # --- ‼️ ВАЖНАЯ ЛОГИКА ‼️ ---
    # Если в сообщении нет "Зміни на..." (как в графиках на 13 и 14),
    # мы используем саму дату графика как уникальный ID (timestamp).
    if not change_time:
        change_time = schedule_date_str # напр. "14.11.2025"
    # ---------------------------
    
    data = {
        "change_timestamp_str": change_time, # Уникальный ID (напр. "21:31 12.11.2025" или "14.11.2025")
        "schedule_date_str": schedule_date_str, # Дата, НА которую график (напр. "14.11.2025")
        "queues": queues
    }
    
    return data, schedule_date_iso

# --- (read_json_file и write_json_file - БЕЗ ИЗМЕНЕНИЙ) ---

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

# --- (main() - БЕЗ ИЗМЕНЕНИЙ, т.к. вся логика в парсере) ---

def main():
    log.info(f"[{datetime.datetime.now()}] Запуск проверки обновлений...")
    
    if not all([API_ID, API_HASH, SESSION_STRING]):
        log.error("Критические секреты (API_ID, API_HASH, SESSION) не установлены. Роботу зупинено.")
        return

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    with client:
        log.info(f"Подключение к Telegram... Чтение канала: {CHANNEL_USERNAME}")
        
        new_data = None
        schedule_date = None
        
        try:
            messages = client.get_messages(CHANNEL_USERNAME, limit=SCAN_LIMIT)
        except Exception as e:
            log.error(f"Ошибка получения сообщений с канала: {e}")
            return
            
        for msg in messages:
            if not msg.text:
                continue
            new_data, schedule_date = parse_schedule_message(msg.text)
            if new_data:
                log.info(f"Найден последний валидный график (ID: {new_data.get('change_timestamp_str')})")
                break 

        if not new_data:
            log.info(f"Не найдено валидных графиков в последних {SCAN_LIMIT} сообщениях. Пропуск.")
            return

        log.info(f"Обработка графика (ID: {new_data['change_timestamp_str']}) на дату {schedule_date}")

        old_latest = read_json_file(LATEST_FILE, {})
        
        if old_latest.get('change_timestamp_str') == new_data.get('change_timestamp_str'):
            log.info("Это тот же график, что и в прошлый раз. Обновление не требуется.")
            return

        log.info("!!! Обнаружен НОВЫЙ график! Обновляем файлы...")

        write_json_file(LATEST_FILE, new_data)
        log.info(f"Файл {LATEST_FILE} обновлен.")

        archive_path = os.path.join(ARCHIVE_DIR, f"{schedule_date}.json")
        write_json_file(archive_path, new_data)
        log.info(f"Файл архива {archive_path} обновлен.")

        index_data = read_json_file(INDEX_FILE, {"available_dates": []})
        if schedule_date not in index_data["available_dates"]:
            index_data["available_dates"].append(schedule_date)
            index_data["available_dates"].sort(reverse=True) 
            write_json_file(INDEX_FILE, index_data)
            log.info(f"Файл {INDEX_FILE} обновлен, добавлена дата {schedule_date}.")
        else:
            log.info(f"Дата {schedule_date} уже есть в индексе.")

if __name__ == "__main__":
    main()