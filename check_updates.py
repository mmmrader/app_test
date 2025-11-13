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

# !!! ЗАМІНІТЬ НА НАЗВУ ВАШОГО КАНАЛУ !!!
CHANNEL_USERNAME = 'SvitloOleksandriyskohoRaionu' 

# Назви файлів та папок
ARCHIVE_DIR = "archive"
LATEST_FILE = "latest.json"
INDEX_FILE = "index.json"

# --- Завантаження Секретів з GitHub Actions ---
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('TELETHON_SESSION')
# -----------------

def parse_schedule_message(text):
    """
    Парсить текстове повідомлення.
    Повертає (data, schedule_date_iso) або (None, None).
    """
    # "Зміни на 21:31 12.11.2025"
    change_time_match = re.search(r'Зміни на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})', text)
    change_time = change_time_match.group(1) if change_time_match else None
    
    # "НЕК "Укренерго" 12.11.2025 внесено зміни"
    schedule_date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4}) внесено зміни', text)
    
    if not schedule_date_match:
        # Якщо не знайшли дату графіка, це не те повідомлення
        return None, None

    # Форматуємо дату в YYYY-MM-DD для імені файлу
    day, month, year = schedule_date_match.groups()
    schedule_date_iso = f"{year}-{month}-{day}" # "2025-11-12"
    
    # "Черга 1.1: 02-04, 09-12, 14-16, 17-20, 22-24"
    queue_matches = re.findall(r'(Черга [\d\.]+): (.*)', text)
    queues = []
    for match in queue_matches:
        queue_name = match[0].replace('Черга ', '').strip()
        times = [t.strip() for t in match[1].split(',')]
        queues.append({"queue_name": queue_name, "times": times})
        
    if not queues:
        # Якщо знайшли дату, але не знайшли черг - це не графік
        return None, None
        
    data = {
        "change_timestamp_str": change_time,
        "schedule_date_str": f"{day}.{month}.{year}", # "12.11.2025"
        "queues": queues
    }
    
    return data, schedule_date_iso

def read_json_file(path, default_data):
    """Безпечно читає JSON."""
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # Якщо файл не знайдено або пошкоджено, повертаємо стандартні дані
        return default_data

def write_json_file(path, data):
    """
    Безпечно записує JSON.
    (Це виправлена версія функції).
    """
    # 1. Отримуємо ім'я директорії
    dir_name = os.path.dirname(path)
    
    # 2. СТВОРЮЄМО ДИРЕКТОРІЮ, ТІЛЬКИ ЯКЩО ВОНА ВЗАГАЛІ Є
    # (Для 'latest.json' -> dir_name буде '', і 'if dir_name' буде False)
    # (Для 'archive/file.json' -> dir_name буде 'archive', і 'if dir_name' буде True)
    if dir_name: 
        os.makedirs(dir_name, exist_ok=True)
        
    # 3. Записуємо сам файл
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    log.info(f"[{datetime.datetime.now()}] Запуск перевірки оновлень...")
    
    if not all([API_ID, API_HASH, SESSION_STRING]):
        log.error("Критичні секрети (API_ID, API_HASH, SESSION) не встановлені. Роботу зупинено.")
        return

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    with client:
        log.info(f"Підключення до Telegram... Читання каналу: {CHANNEL_USERNAME}")
        try:
            # Отримуємо останнє повідомлення з каналу
            last_message = client.get_messages(CHANNEL_USERNAME, limit=1)[0]
        except Exception as e:
            log.error(f"Помилка отримання повідомлення з каналу: {e}")
            return
            
        new_data, schedule_date = parse_schedule_message(last_message.text)
        
        if not new_data:
            log.info("Останнє повідомлення не схоже на графік. Пропуск.")
            return

        log.info(f"Розпізнано графік від {new_data['change_timestamp_str']} на дату {schedule_date}")

        # --- Головна логіка: Порівняння ---
        
        # 1. Завантажуємо старий latest.json для порівняння
        old_latest = read_json_file(LATEST_FILE, {})
        
        # Порівнюємо по часу зміни. Якщо час той самий, нічого не робимо.
        if old_latest.get('change_timestamp_str') == new_data.get('change_timestamp_str'):
            log.info("Це той самий графік, що і минулого разу. Оновлення не потрібне.")
            return

        log.info("!!! Виявлено НОВИЙ графік! Оновлюємо файли...")

        # 2. Зберігаємо новий LATEST.JSON
        write_json_file(LATEST_FILE, new_data)
        log.info(f"Файл {LATEST_FILE} оновлено.")

        # 3. Зберігаємо копію в АРХІВ (наприклад, archive/2025-11-12.json)
        archive_path = os.path.join(ARCHIVE_DIR, f"{schedule_date}.json")
        write_json_file(archive_path, new_data)
        log.info(f"Файл архіву {archive_path} оновлено.")

        # 4. Оновлюємо INDEX.JSON (список всіх дат в архіві)
        index_data = read_json_file(INDEX_FILE, {"available_dates": []})
        if schedule_date not in index_data["available_dates"]:
            index_data["available_dates"].append(schedule_date)
            # Сортуємо, щоб новіші дати були вгорі списку
            index_data["available_dates"].sort(reverse=True) 
            write_json_file(INDEX_FILE, index_data)
            log.info(f"Файл {INDEX_FILE} оновлено, додано дату {schedule_date}.")
        else:
            log.info(f"Дата {schedule_date} вже є в індексі.")

if __name__ == "__main__":
    main()