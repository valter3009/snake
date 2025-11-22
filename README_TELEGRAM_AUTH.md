# 🔐 Инструкция по настройке Telegram авторизации

Для парсинга Telegram каналов требуется **один раз** выполнить авторизацию.

## Шаг 1: Получите Telegram API credentials

1. Зайдите на https://my.telegram.org/apps
2. Войдите под своим номером телефона
3. Создайте приложение (любое название, например "News Bot")
4. Скопируйте **api_id** и **api_hash**

## Шаг 2: Добавьте credentials в .env

Откройте файл `.env` и добавьте (или обновите):

```env
# Telegram Client API (для парсинга каналов)
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=ваш_api_hash_здесь
TELEGRAM_PHONE=+79001234567
```

**⚠️ Важно:**
- `TELEGRAM_PHONE` должен быть в международном формате с `+` (например: `+79001234567`)
- Убедитесь, что переменная `NEWS_API_KEY` **удалена** из .env (она больше не используется)

## Шаг 3: Установите зависимости локально

```bash
pip install -r requirements.txt
```

## Шаг 4: Запустите скрипт авторизации

```bash
python auth_telegram.py
```

### Что произойдет:

1. Скрипт отправит SMS код на ваш номер телефона
2. Вам нужно будет ввести код из SMS
3. Если у вас включен 2FA, потребуется ввести пароль
4. После успешной авторизации создастся файл `data/news_collector.session`

**Пример вывода:**

```
============================================================
🔐 АВТОРИЗАЦИЯ В TELEGRAM
============================================================
📱 Телефон: +79001234567
📁 Файл сессии: C:\Users\Home\Desktop\bots\NewsTg\data\news_collector.session

⏳ Подключаюсь к Telegram...
📲 Отправляю код авторизации на номер: +79001234567
✏️ Введите код из Telegram: 12345

✅ Успешно авторизован!
👤 Имя: Иван Иванов
📱 Номер: +79001234567
🆔 ID: 123456789

============================================================
✅ Файл сессии создан: data\news_collector.session
============================================================

Теперь можете запустить бота в Docker.
```

## Шаг 5: Запустите бота в Docker

После создания файла сессии, запустите бота как обычно:

```bash
git merge --abort || echo Merge aborted & git fetch origin claude/add-international-news-sources-01DtoHTVdEyU2H9TRuFYHqVW & git checkout claude/add-international-news-sources-01DtoHTVdEyU2H9TRuFYHqVW & git pull & docker build -t news-bot . & docker stop news-telegram-bot & docker rm news-telegram-bot & docker run -d --name news-telegram-bot --env-file .env -v %cd%\data:/app/data news-bot & docker logs -f news-telegram-bot
```

Файл `data/news_collector.session` автоматически смонтируется в Docker контейнер и будет использоваться для авторизации.

## ❓ Возможные проблемы

### Ошибка "EOF when reading a line"
Это означает, что файл сессии не найден или невалиден. Запустите `auth_telegram.py` еще раз.

### Ошибка "Phone number is invalid"
Проверьте формат номера в `.env` - должен начинаться с `+` (например: `+79001234567`)

### Ошибка "Two-step verification is enabled"
Введите пароль 2FA когда скрипт попросит.

## 📝 Примечания

- Файл сессии `data/news_collector.session` действителен **долгое время** (месяцы/годы)
- После создания сессии повторная авторизация **не требуется**
- Файл сессии содержит авторизационные данные - **НЕ** публикуйте его
- Если нужно переавторизоваться - просто удалите файл сессии и запустите `auth_telegram.py` снова
