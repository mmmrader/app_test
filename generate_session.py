from telethon.sync import TelegramClient
from telethon.sessions import StringSession

# Вставьте свои ID и Hash сюда
API_ID = 33067680 
API_HASH = 'bc363088d2d73599c75824845e2956c9'

print("Запускаем генератор сессии...")
print("Вам придет код от Telegram. Введите его.")

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    # При первом запуске запросит номер телефона и код
    session_string = client.session.save()

print("\n--- ВАША СЕССИЯ (TELETHON_SESSION) ---")
print(session_string)
print("---------------------------------------")
print("Скопируйте эту длинную строку (без кавычек) и вставьте в GitHub Secrets.")