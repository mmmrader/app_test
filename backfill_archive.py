import os
import re
import json
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import logging

# --- ‼️ ВСТАВЬТЕ ВАШИ ДАННЫЕ ‼️ ---
API_ID = 33067680 # Ваш API ID
API_HASH = "bc363088d2d73599c75824845e2956c9" # Ваш API Hash
SESSION_STRING = "1ApWapzMBu4o-t2RzvH8CsKshPvoT1nOLyGwhfyHsJAVNL_yk_HGuiCBhPTdlWFt04Z1RxKC1XfPE89wnEYtMRbTKoHmQWMjmuKNgfKn3v2oodUzguos_fO6Bk_ZXV6RP-nBo_9fgfRGqwW2Fac-XabsmsX6Q5jrMgx1DSO7M0fb3TZY6e60IYDrxZho2sLz43qfOMOsOCm8BsQhVpFxejbaAk_iwjes6PPX54rLY2RcrzMpni7wvpkVI113_9wb0AXQngg4NgdYG6VdLjnmZOwYduFXm0PFk-M4RvMBAenPwkqXapzjF3Wq4HJj8FdrrpREuhjmXJTWbQbjCiJi3evL0_YZJNOE=" # Ваша TELETHON_SESSION
CHANNEL_USERNAME = "SvitloOleksandriyskohoRaionu"
SCAN_LIMIT = 20 # Скануємо останні 20 повідомлень для кожного каналу

# Список регіонів (Той самий, що і в check_updates.py)
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

BASE_OUTPUT_DIR = "api"

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

def parse_schedule_message(text):
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

def write_json_file(path, data):
    dir_name = os.path.dirname(path)
    if dir_name: os.makedirs(dir_name, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main_backfill():
    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)
    
    with client:
        # ПРОХОДИМО ПО КОЖНОМУ РЕГІОНУ
        for region_id, channel_username in REGIONS.items():
            log.info(f"--- Сканування: {region_id} ({channel_username}) ---")
            
            # Шляхи для конкретного регіону: api/region_id/...
            region_dir = os.path.join(BASE_OUTPUT_DIR, region_id)
            latest_file = os.path.join(region_dir, "latest.json")
            archive_dir = os.path.join(region_dir, "archive")
            index_file = os.path.join(region_dir, "index.json")
            
            all_schedules = {} 

            try:
                messages = client.get_messages(channel_username, limit=SCAN_LIMIT)
                for msg in messages:
                    if not msg.text: continue
                    new_data, schedule_date = parse_schedule_message(msg.text)
                    
                    if new_data:
                        if schedule_date not in all_schedules:
                            log.info(f"  Знайдено графік: {schedule_date}")
                            all_schedules[schedule_date] = new_data
            except Exception as e:
                log.error(f"  Помилка каналу {channel_username}: {e}")
                continue

            if not all_schedules:
                log.warning(f"  Графіків не знайдено.")
                continue

            # 1. Зберігаємо архів
            for date_iso, data in all_schedules.items():
                write_json_file(os.path.join(archive_dir, f"{date_iso}.json"), data)

            # 2. Створюємо індекс
            available_dates = sorted(all_schedules.keys(), reverse=True)
            index_data = {"available_dates": available_dates}
            write_json_file(index_file, index_data)
            
            # 3. Створюємо latest.json
            if available_dates:
                latest_data = all_schedules[available_dates[0]]
                write_json_file(latest_file, latest_data)
                log.info(f"  Успішно збережено latest.json для {region_id}")

    print("\n✅ Готово! Тепер зробіть: git add . && git commit -m 'Add regions' && git push")

if __name__ == "__main__":
    main_backfill()