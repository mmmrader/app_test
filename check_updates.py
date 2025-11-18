import os
import re
import json
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import logging

# --- НАЛАШТУВАННЯ ---
logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('TELETHON_SESSION')
SCAN_LIMIT = 10

# Список всіх регіонів (ID -> Username каналу)
REGIONS = {
    "oleksandriya": "SvitloOleksandriyskohoRaionu",
    "blagovischenske": "SvitloBlagovishenskogoRajonu",
    "holovanivsk": "SvitloHolovanivskohoRayonu",
    "znamianka": "znamelektro",
    "kompaniivka": "SvitloKompanievskohoRaionu",
    "novoarkhangelsk": "SvitloNovoarhangelsk_REM",
    "oleksandrivka": "SvitloOleksandrivskogoRaionu",
    "petrove": "SvitloPetrivskohoRaionu",
    "bobrynets": "SvitloBobrynetskohoRaionu",
    "dobrovelychkivka": "SvitloDobrovelychkivskogoRaionu",
    "kropyvnytskyi_city": "SvitloKropyvnytskyiMisto",
    "kropyvnytskyi_district": "SvitloKropyvnytskohoRaionu",
    "malovyskiv": "SvitloMalovyskivskohoRaionu",
    "novomyrhorod": "novomyrhorod1",
    "svitlovodsk": "SvitloSvitlovodskohoRaionu",
    "haivoron": "SvitloGaivoronskiyRaionu",
    "dolynska": "SvitloDolinskogoRaionu",
    "kamianets": "rem_ng",
    "novoukrainka": "SvitloNovoukrainskogoRaionu",
    "onufriivka": "SvitloOnufriivskohoRaionu"
}

BASE_OUTPUT_DIR = "api" # Папка, де будуть лежати підпапки регіонів

def parse_schedule_message(text):
    # Універсальний парсер (підтримує обидва формати)
    date_pattern = r"За розпорядженням НЕК \"Укренерго\" (\d{2})\.(\d{2})\.(\d{4}) (?:буде діяти|внесено зміни)"
    schedule_date_match = re.search(date_pattern, text)
    if not schedule_date_match: return None, None
    
    day, month, year = schedule_date_match.groups()
    schedule_date_str = f"{day}.{month}.{year}"
    schedule_date_iso = f"{year}-{month}-{day}"
    
    change_time_match = re.search(r'Зміни на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})', text)
    change_time = change_time_match.group(1) if change_time_match else None
    
    queue_matches = re.findall(r'(Черга [\d\.]+): (.*)', text)
    queues = []
    for match in queue_matches:
        queue_name = match[0].replace('Черга ', '').strip()
        times = [t.strip() for t in match[1].split(',')]
        queues.append({"queue_name": queue_name, "times": times})
        
    if not queues: return None, None
    
    if not change_time:
        change_time = schedule_date_str 
        
    data = {
        "change_timestamp_str": change_time,
        "schedule_date_str": schedule_date_str,
        "queues": queues
    }
    return data, schedule_date_iso

def read_json_file(path, default_data):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except: return default_data

def write_json_file(path, data):
    dir_name = os.path.dirname(path)
    if dir_name: os.makedirs(dir_name, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def process_region(client, region_id, channel_username):
    log.info(f"--- Обробка регіону: {region_id} ---")
    
    # Структура: api/{region_id}/latest.json
    region_dir = os.path.join(BASE_OUTPUT_DIR, region_id)
    latest_file = os.path.join(region_dir, "latest.json")
    archive_dir = os.path.join(region_dir, "archive")
    index_file = os.path.join(region_dir, "index.json")

    new_data = None
    schedule_date = None

    try:
        messages = client.get_messages(channel_username, limit=SCAN_LIMIT)
        for msg in messages:
            if not msg.text: continue
            data, date = parse_schedule_message(msg.text)
            if data:
                new_data = data
                schedule_date = date
                break
    except Exception as e:
        log.error(f"Помилка каналу {channel_username}: {e}")
        return

    if not new_data:
        log.info(f"Графіків не знайдено.")
        return

    old_latest = read_json_file(latest_file, {})
    if old_latest.get('change_timestamp_str') == new_data.get('change_timestamp_str'):
        log.info("Дані актуальні.")
        return

    log.info(f"!!! Оновлення даних !!!")
    write_json_file(latest_file, new_data)
    write_json_file(os.path.join(archive_dir, f"{schedule_date}.json"), new_data)
    
    index_data = read_json_file(index_file, {"available_dates": []})
    if schedule_date not in index_data["available_dates"]:
        index_data["available_dates"].append(schedule_date)
        index_data["available_dates"].sort(reverse=True)
        write_json_file(index_file, index_data)

def main():
    if not all([API_ID, API_HASH, SESSION_STRING]):
        log.error("Секрети не знайдено.")
        return

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    with client:
        for region_id, channel in REGIONS.items():
            process_region(client, region_id, channel)

if __name__ == "__main__":
    main()