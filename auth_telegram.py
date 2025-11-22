#!/usr/bin/env python3
"""
Скрипт для первоначальной авторизации в Telegram.
Запустите этот скрипт ОДИН РАЗ локально, чтобы создать файл сессии.
После этого файл news_collector.session можно использовать в Docker.
"""

import asyncio
import os
from pathlib import Path
from telethon import TelegramClient
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

TELEGRAM_API_ID = int(os.getenv("TELEGRAM_API_ID"))
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
TELEGRAM_PHONE = os.getenv("TELEGRAM_PHONE")

# Путь к файлу сессии (в папке data)
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
SESSION_FILE = DATA_DIR / "news_collector.session"

async def main():
    print("=" * 60)
    print("🔐 АВТОРИЗАЦИЯ В TELEGRAM")
    print("=" * 60)
    print(f"📱 Телефон: {TELEGRAM_PHONE}")
    print(f"📁 Файл сессии: {SESSION_FILE}")
    print()

    # Создаем клиента
    client = TelegramClient(
        str(SESSION_FILE),
        TELEGRAM_API_ID,
        TELEGRAM_API_HASH
    )

    try:
        # Подключаемся и авторизуемся
        print("⏳ Подключаюсь к Telegram...")
        await client.connect()

        if not await client.is_user_authorized():
            print("📲 Отправляю код авторизации на номер:", TELEGRAM_PHONE)
            await client.send_code_request(TELEGRAM_PHONE)

            # Запрашиваем код
            code = input("✏️ Введите код из Telegram: ")

            try:
                await client.sign_in(TELEGRAM_PHONE, code)
            except Exception as e:
                # Если требуется 2FA пароль
                if "password" in str(e).lower():
                    password = input("🔒 Введите пароль 2FA: ")
                    await client.sign_in(password=password)
                else:
                    raise

        # Проверяем, что авторизованы
        me = await client.get_me()
        print()
        print("✅ Успешно авторизован!")
        print(f"👤 Имя: {me.first_name} {me.last_name or ''}")
        print(f"📱 Номер: {me.phone}")
        print(f"🆔 ID: {me.id}")
        print()
        print("=" * 60)
        print(f"✅ Файл сессии создан: {SESSION_FILE}")
        print("=" * 60)
        print()
        print("Теперь можете запустить бота в Docker.")
        print("Файл сессии будет автоматически использован.")

    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
