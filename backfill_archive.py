import os
import re
import json
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import logging

# --- ‼️ ВСТАВТЕ ВАШІ ДАНІ ‼️ ---
API_ID = 33067680 # Ваш API ID
API_HASH = "bc363088d2d73599c75824845e2956c9" # Ваш API Hash
SESSION_STRING = "1ApWapzMBu4o-t2RzvH8CsKshPvoT1nOLyGwhfyHsJAVNL_yk_HGuiCBhPTdlWFt04Z1RxKC1XfPE89wnEYtMRbTKoHmQWMjmuKNgfKn3v2oodUzguos_fO6Bk_ZXV6RP-nBo_9fgfRGqwW2Fac-XabsmsX6Q5jrMgx1DSO7M0fb3TZY6e60IYDrxZho2sLz43qfOMOsOCm8BsQhVpFxejbaAk_iwjes6PPX54rLY2RcrzMpni7wvpkVI113_9wb0AXQngg4NgdYG6VdLjnmZOwYduFXm0PFk-M4RvMBAenPwkqXapzjF3Wq4HJj8FdrrpREuhjmXJTWbQbjCiJi3evL0_YZJNOE=" # Ваша TELETHON_SESSION
CHANNEL_USERNAME = "SvitloOleksandriyskohoRaionu"
SCAN_LIMIT = 500 # Скільки останніх повідомлень сканувати
# -----------------------------

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

ARCHIVE_DIR = "archive"
INDEX_FILE = "index.json"

# --- Функції, скопійовані з check_updates.py ---

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

def write_json_file(path, data):
    dir_name = os.path.dirname(path)
    if dir_name: 
        os.makedirs(dir_name, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Головна функція ---

def main_backfill():
    log.info(f"Початок сканування {SCAN_LIMIT} повідомлень з {CHANNEL_USERNAME}...")
    
    # Словник для зберігання { "2025-11-12": data, ... }
    # Це автоматично збереже лише ОСТАННЄ оновлення за кожен день
    all_schedules = {} 
    
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    with client:
        log.info("Підключено. Отримання повідомлень...")
        messages = client.get_messages(CHANNEL_USERNAME, limit=SCAN_LIMIT)
        
        for msg in messages:
            if not msg.text:
                continue
                
            new_data, schedule_date = parse_schedule_message(msg.text)
            
            if new_data:
                # Зберігаємо у словник. Новіші поверх старих.
                if schedule_date not in all_schedules:
                    log.info(f"Знайдено графік на дату: {schedule_date}")
                    all_schedules[schedule_date] = new_data

    if not all_schedules:
        log.warning("Не знайдено жодного графіка.")
        return

    log.info(f"\nЗнайдено {len(all_schedules)} унікальних графіків.")
    
    # 1. Зберігаємо всі файли в архів
    for date_iso, data in all_schedules.items():
        archive_path = os.path.join(ARCHIVE_DIR, f"{date_iso}.json")
        write_json_file(archive_path, data)

    log.info(f"Папку {ARCHIVE_DIR} заповнено.")

    # 2. Створюємо index.json
    available_dates = sorted(all_schedules.keys(), reverse=True)
    index_data = {"available_dates": available_dates}
    write_json_file(INDEX_FILE, index_data)
    log.info(f"Файл {INDEX_FILE} створено.")

    print("\n[V] Заповнення архіву завершено! Тепер можна завантажити (push) папку 'archive' та 'index.json' у репозиторій.")

if __name__ == "__main__":
    main_backfill()