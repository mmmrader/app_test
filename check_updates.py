import os
import re
import json
import datetime
from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# --- Настройки ---
# Имя файла, где будет лежать последнее расписание
JSON_FILE_NAME = 'latest_schedule.json' 
# Имя пользователя канала (публичного)
CHANNEL_USERNAME = 'app_test' # <-- ЗАМЕНИТЕ НА ИМЯ КАНАЛА
# -----------------

# --- Загрузка Секретов из GitHub Actions ---
API_ID = os.environ.get('API_ID')
API_HASH = os.environ.get('API_HASH')
SESSION_STRING = os.environ.get('TELETHON_SESSION')
# -----------------

def parse_schedule_message(text):
    """
    Парсит текстовое сообщение.
    (Код парсера из нашего прошлого ответа)
    """
    change_time_match = re.search(r'Зміни на (\d{2}:\d{2} \d{2}\.\d{2}\.\d{4})', text)
    change_time = change_time_match.group(1) if change_time_match else None
    
    schedule_date_match = re.search(r'(\d{2}\.\d{2}\.\d{4}) внесено зміни', text)
    schedule_date = schedule_date_match.group(1) if schedule_date_match else None
    
    queue_matches = re.findall(r'(Черга [\d\.]+): (.*)', text)
    
    queues = []
    for match in queue_matches:
        queue_name = match[0].replace('Черга ', '').strip()
        times = [t.strip() for t in match[1].split(',')]
        queues.append({"queue_name": queue_name, "times": times})
        
    if not queues:
        return None
        
    return {
        "change_timestamp_str": change_time,
        "schedule_date_str": schedule_date,
        "queues": queues
    }

def read_old_data():
    """Читает старые данные из JSON-файла, если он есть."""
    try:
        with open(JSON_FILE_NAME, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        print("Файл latest_schedule.json не найден. Будет создан новый.")
        return {} # Возвращаем пустой словарь, если файла нет
    except json.JSONDecodeError:
        print("Ошибка чтения JSON. Файл будет перезаписан.")
        return {}

def main():
    print(f"[{datetime.datetime.now()}] Запуск проверки обновлений...")
    
    if not API_ID or not API_HASH or not SESSION_STRING:
        print("Ошибка: Секреты API_ID, API_HASH или TELETHON_SESSION не установлены.")
        return

    client = TelegramClient(StringSession(SESSION_STRING), API_ID, API_HASH)

    with client:
        print(f"Подключение к Telegram... Чтение канала: {CHANNEL_USERNAME}")
        # Получаем последнее сообщение из канала
        try:
            last_message = client.get_messages(CHANNEL_USERNAME, limit=1)[0]
        except Exception as e:
            print(f"Ошибка получения сообщения из канала: {e}")
            return
            
        print("Получено последнее сообщение. Начинаем парсинг...")
        new_data = parse_schedule_message(last_message.text)
        
        if not new_data:
            print("Сообщение не похоже на график. Обновление не требуется.")
            return

        print(f"Распознан график от: {new_data.get('change_timestamp_str')}")
        
        # --- Главная логика: Сравнение ---
        old_data = read_old_data()
        
        # Сравниваем по времени изменения. Если время то же, ничего не делаем.
        if old_data.get('change_timestamp_str') == new_data.get('change_timestamp_str'):
            print("Это тот же график, что и в прошлый раз. Обновление не требуется.")
        else:
            print("!!! Обнаружен НОВЫЙ график! Запись в файл...")
            # Записываем новые данные в файл
            with open(JSON_FILE_NAME, 'w', encoding='utf-8') as f:
                json.dump(new_data, f, ensure_ascii=False, indent=4)
            print(f"Файл {JSON_FILE_NAME} успешно обновлен.")

if __name__ == "__main__":
    main()