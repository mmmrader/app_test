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

CHANNEL_USERNAME = 'SvitloOleksandriyskohoRaionu' # <-- ЗАМЕНИТЕ
ARCHIVE_DIR = "archive"
LATEST_FILE = "latest.json"
INDEX_FILE = "index.json"

# --- Загрузка Секретов ---
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('TELETHON_SESSION')

def parse_schedule_message(text):
    """Парсит текстовое сообщение."""
    change_time_match = re.search(r'Зміни на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})', text)
    change_time = change_time_match.group(1) if change_time_match else None
    
    # Ищем дату, НА которую действует график (важнейшее поле)
    # "НЕК "Укренерго" 12.11.2025 внесено зміни"
    schedule_date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4}) внесено зміни', text)
    
    if not schedule_date_match:
        # Если не нашли дату графика, это не то сообщение
        return None, None

    # Форматируем дату в YYYY-MM-DD для имени файла
    day, month, year = schedule_date_match.groups()
    schedule_date_iso = f"{year}-{month}-{day}" # "2025-11-12"
    
    queue_matches = re.findall(r'(Черга [\d\.]+): (.*)', text)
    queues = []
    for match in queue_matches:
        queue_name = match[0].replace('Черга ', '').strip()
        times = [t.strip() for t in match[1].split(',')]
        queues.append({"queue_name": queue_name, "times": times})
        
    if not queues:
        return None, None
        
    data = {
        "change_timestamp_str": change_time,
        "schedule_date_str": f"{day}.{month}.{year}", # "12.11.2025"
        "queues": queues
    }
    
    return data, schedule_date_iso

def read_json_file(path, default_data):
    """Безопасно читает JSON."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default_data

def write_json_file(path, data):
    """Записывает JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    log.info("Запуск проверки обновлений...")
    
    if not all([API_ID, API_HASH, SESSION_STRING]):
        log.error("Критические секреты (API_ID, API_HASH, SESSION) не найдены.")
        return

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    with client:
        log.info(f"Подключение к Telegram... Чтение канала: {CHANNEL_USERNAME}")
        try:
            last_message = client.get_messages(CHANNEL_USERNAME, limit=1)[0]
        except Exception as e:
            log.error(f"Ошибка получения сообщения: {e}")
            return
            
        new_data, schedule_date = parse_schedule_message(last_message.text)
        
        if not new_data:
            log.info("Сообщение не похоже на график. Пропуск.")
            return

        log.info(f"Распознан график от {new_data['change_timestamp_str']} на дату {schedule_date}")

        # --- Логика Архива ---
        # 1. Загружаем старый latest.json для сравнения
        old_latest = read_json_file(LATEST_FILE, {})
        
        if old_latest.get('change_timestamp_str') == new_data.get('change_timestamp_str'):
            log.info("Это тот же график, что и в прошлый раз. Обновление не требуется.")
            return

        log.info("!!! Обнаружен НОВЫЙ график! Обновляем файлы...")

        # 2. Сохраняем новый LATEST.JSON
        write_json_file(LATEST_FILE, new_data)
        log.info(f"Файл {LATEST_FILE} обновлен.")

        # 3. Сохраняем копию в АРХИВ (например, archive/2025-11-12.json)
        archive_path = os.path.join(ARCHIVE_DIR, f"{schedule_date}.json")
        write_json_file(archive_path, new_data)
        log.info(f"Файл архива {archive_path} обновлен.")

        # 4. Обновляем INDEX.JSON (список всех дат в архиве)
        index_data = read_json_file(INDEX_FILE, {"available_dates": []})
        if schedule_date not in index_data["available_dates"]:
            index_data["available_dates"].append(schedule_date)
            # Сортируем, чтобы новые даты были вверху
            index_data["available_dates"].sort(reverse=True) 
            write_json_file(INDEX_FILE, index_data)
            log.info(f"Файл {INDEX_FILE} обновлен, добавлена дата {schedule_date}.")

if __name__ == "__main__":
    main()