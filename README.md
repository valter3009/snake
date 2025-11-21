# Telegram News Bot с аналитикой Claude AI

Профессиональный Telegram бот для автоматического сбора, анализа и публикации новостей с глубокой политической аналитикой.

## Возможности

- Автоматический сбор новостей из RSS и NewsAPI
- Анализ и отбор топовых новостей через Claude AI
- Генерация глубокой политической аналитики
- Система модерации постов
- Публикация с медиа (фото/видео)
- Детальная статистика и логирование
- Автоматическая публикация по расписанию
- PostgreSQL для отслеживания публикаций

## Технологии

- **Python**: 3.11
- **AI**: Claude 3.5 Sonnet (Anthropic)
- **Database**: PostgreSQL (asyncpg)
- **Telegram**: python-telegram-bot 21.7
- **News**: NewsAPI, RSS feeds
- **Deployment**: Docker, Railway

## Структура проекта

```
bot/
├── core/           # Базовая функциональность
│   ├── database.py    # PostgreSQL (asyncpg)
│   ├── logger.py      # Цветное логирование
│   ├── exceptions.py  # Кастомные исключения
│   └── __init__.py
├── news/           # Сбор и анализ новостей
│   ├── collector.py   # Сбор из RSS и NewsAPI
│   ├── analyzer.py    # Анализ через Claude
│   ├── extractor.py   # Извлечение текста
│   ├── sources.py     # Источники новостей
│   └── __init__.py
├── content/        # Генерация контента
│   ├── generator.py   # Генерация постов
│   ├── prompts.py     # Промпты для Claude
│   ├── formatter.py   # Форматирование
│   └── __init__.py
├── telegram/       # Telegram функциональность
│   ├── handlers.py    # Обработчики команд
│   ├── moderator.py   # Модерация постов
│   ├── publisher.py   # Публикация в канал
│   └── __init__.py
├── media/          # Обработка медиа
│   ├── handler.py     # Обработка изображений
│   ├── optimizer.py   # Оптимизация
│   └── __init__.py
├── scheduler/      # Планировщик
│   ├── tasks.py       # Автоматизация
│   └── __init__.py
├── config.py       # Конфигурация
└── main.py         # Точка входа
```

## Переменные окружения

Все переменные настроены в Railway:

```env
# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_ADMIN_ID=your_telegram_id
TELEGRAM_CHANNEL_ID=@your_channel

# Claude AI
ANTHROPIC_API_KEY=sk-ant-api03-xxx

# NewsAPI
NEWS_API_KEY=your_newsapi_key

# Database
DATABASE_URL=postgresql://...

# Settings
TIMEZONE=Europe/Moscow
LOG_LEVEL=INFO
MIN_POSTS_PER_DAY=40
MAX_POSTS_PER_DAY=50
```

## Команды бота

- `/start` - Запуск бота и справка
- `/status` - Статус и статистика
- `/stats` - Детальная статистика
- `/health` - Проверка здоровья системы
- `/publish` - Принудительная публикация

## Deployment в Railway

Бот автоматически деплоится через Docker:

1. Railway автоматически обнаруживает Dockerfile
2. Собирает образ
3. Запускает контейнер
4. Использует переменные окружения из Railway

## Архитектура

```
Сбор новостей → Анализ Claude → Генерация постов → Модерация → Публикация
     ↓              ↓                ↓                ↓            ↓
   RSS/API      Top N выбор      Аналитика       Админ OK      Канал
```

## Особенности реализации

### База данных
- ТОЛЬКО asyncpg (без psycopg2)
- Connection pooling
- Graceful shutdown
- Все вызовы обернуты в `if db_manager:`

### Логирование
- Цветное логирование с colorlog
- Эмодзи для визуализации
- Детальная трассировка на каждом этапе

### Обработка ошибок
- Try/except на всех критических операциях
- Fallback механизмы
- Продолжение работы при частичных сбоях

### Контент
- Промпты оптимизированы для глубокого анализа
- Проверка качества через Claude
- Валидация длины и структуры

## Автор

Создано для профессиональной новостной аналитики на уровень выше обычных каналов.
