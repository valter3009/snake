# 🚂 Деплой на Railway - Инструкция

## Переменные окружения для Railway

Добавьте следующие переменные в Railway (Variables):

### 1. TELEGRAM_BOT_TOKEN
```
Получите у @BotFather в Telegram:
1. Напишите @BotFather
2. /newbot
3. Следуйте инструкциям
4. Скопируйте токен

Формат: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz
```

### 2. TELEGRAM_CHANNEL_ID
```
Создайте канал и получите ID:
1. Создайте канал в Telegram
2. Добавьте бота в админы канала (права на публикацию)
3. Для публичного канала: @channel_username
4. Для приватного канала: -1001234567890

Формат: @mynewschannel ИЛИ -1001234567890
```

### 3. TELEGRAM_ADMIN_ID
```
Получите ваш Telegram ID:
1. Напишите @userinfobot в Telegram
2. Скопируйте ваш ID (число)

Формат: 123456789
```

### 4. ANTHROPIC_API_KEY
```
Получите на https://console.anthropic.com/:
1. Зарегистрируйтесь/войдите
2. API Keys → Create Key
3. Скопируйте ключ

Формат: sk-ant-api03-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 5. NEWS_API_KEY
```
Получите на https://newsapi.org/:
1. Зарегистрируйтесь (бесплатно)
2. Account → API Key
3. Скопируйте ключ

Формат: xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

### 6. DATABASE_URL
```
⚠️ НЕ ДОБАВЛЯЙТЕ ВРУЧНУЮ!

Railway автоматически создаст эту переменную при добавлении PostgreSQL.
```

---

## Пошаговая инструкция деплоя

### Шаг 1: Создайте проект в Railway

1. Зайдите на https://railway.app/
2. Login → Login with GitHub
3. New Project → Deploy from GitHub repo
4. Выберите: **valter3009/snake**
5. Выберите ветку: **claude/complete-redesign-011CUzfzwLCaK56YuygwmyL6**

### Шаг 2: Добавьте PostgreSQL

1. В проекте нажмите "+ New"
2. Database → Add PostgreSQL
3. ✅ Переменная DATABASE_URL создастся автоматически

### Шаг 3: Настройте переменные

1. Кликните на ваш сервис (НЕ на PostgreSQL)
2. Перейдите в "Variables"
3. Нажмите "New Variable" для каждой:

```
TELEGRAM_BOT_TOKEN=ваш_токен
TELEGRAM_CHANNEL_ID=@ваш_канал
TELEGRAM_ADMIN_ID=ваш_id
ANTHROPIC_API_KEY=ваш_ключ
NEWS_API_KEY=ваш_ключ
```

### Шаг 4: Деплой

Railway автоматически задеплоит после добавления переменных.

Следите за логами: Deployments → View Logs

### Шаг 5: Проверка

1. В логах должно появиться: **"Бот запущен и готов к работе!"**
2. Напишите боту в Telegram: `/start`
3. Проверьте статус: `/status`
4. Тест публикации: `/publish`

---

## ✅ Чеклист

- [ ] PostgreSQL добавлен в Railway
- [ ] Все 5 переменных добавлены (DATABASE_URL автоматически)
- [ ] Бот добавлен в админы канала
- [ ] Бот получил права на публикацию в канале
- [ ] Деплой успешен (логи без ошибок)
- [ ] Бот отвечает на команды в Telegram

---

## 🔍 Проверка логов

Правильный запуск выглядит так:

```
INFO - Инициализация бота...
INFO - Конфигурация загружена
INFO - База данных инициализирована
INFO - Бот инициализирован
INFO - Запуск бота...
INFO - Бот запущен и работает
```

## ❌ Типичные ошибки

### "Missing environment variables"
```
ERROR - Отсутствуют обязательные переменные окружения: TELEGRAM_ADMIN_ID, NEWS_API_KEY
```
**Решение:** Добавьте недостающие переменные в Variables

### "TelegramError: Unauthorized"
```
ERROR - Telegram error: Unauthorized
```
**Решение:** Проверьте TELEGRAM_BOT_TOKEN

### "Can't send message to channel"
```
ERROR - Can't send message to channel
```
**Решение:**
1. Бот добавлен в админы канала?
2. У бота есть права на публикацию?
3. TELEGRAM_CHANNEL_ID правильный?

---

## 💡 Советы

1. **Сначала добавьте PostgreSQL**, затем переменные
2. **Не добавляйте DATABASE_URL вручную** - Railway создаст её автоматически
3. **Проверяйте логи** после каждого изменения
4. **Используйте /status** для проверки работы бота

---

## 📞 Нужна помощь?

Если что-то не работает:
1. Проверьте все переменные (Variables)
2. Посмотрите логи (Deployments → View Logs)
3. Убедитесь, что PostgreSQL запущен
4. Создайте Issue в репозитории
