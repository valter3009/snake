"""
Конфигурация для Telegram новостного бота
"""

import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# API ключи
TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_CHANNEL_ID = os.getenv('TELEGRAM_CHANNEL_ID')  # Формат: @channel_name или -100123456789
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

# Настройки базы данных
DATABASE_PATH = 'news_database.db'

# Источники новостей (RSS фиды)
NEWS_SOURCES = [
    {
        'name': 'ТАСС',
        'url': 'https://tass.ru/rss/v2.xml',
        'category': 'общие'
    },
    {
        'name': 'РИА Новости',
        'url': 'https://ria.ru/export/rss2/archive/index.xml',
        'category': 'общие'
    },
    {
        'name': 'Интерфакс',
        'url': 'https://www.interfax.ru/rss.asp',
        'category': 'общие'
    },
    {
        'name': 'Коммерсантъ',
        'url': 'https://www.kommersant.ru/RSS/main.xml',
        'category': 'деловые'
    },
    {
        'name': 'Ведомости',
        'url': 'https://www.vedomosti.ru/rss/news',
        'category': 'деловые'
    },
    {
        'name': 'Хабр',
        'url': 'https://habr.com/ru/rss/news/',
        'category': 'технологии'
    },
    {
        'name': 'CNews',
        'url': 'https://www.cnews.ru/inc/rss/news.xml',
        'category': 'технологии'
    }
]

# Настройки парсинга
MIN_IMAGE_WIDTH = 400  # Минимальная ширина изображения
MIN_IMAGE_HEIGHT = 300  # Минимальная высота изображения
ALLOWED_IMAGE_FORMATS = ['JPEG', 'PNG', 'WebP']
REQUEST_TIMEOUT = 10  # Таймаут для HTTP запросов в секундах
MAX_RETRIES = 3  # Максимальное количество повторных попыток

# Настройки публикации
POSTS_PER_DAY = 8  # Количество постов в день
POST_TIMES = [
    '08:00',
    '10:00',
    '12:00',
    '14:00',
    '16:00',
    '18:00',
    '20:00',
    '22:00'
]  # Время публикации постов (московское время)

# Промпт для Claude API
CLAUDE_PROMPT_TEMPLATE = """Ты - редактор новостного Telegram канала.

Твоя задача: создать привлекательный пост для Telegram на основе следующей новости.

НОВОСТЬ:
Заголовок: {title}
Описание: {description}
Источник: {source}

ТРЕБОВАНИЯ К ПОСТУ:
1. Создай цепляющий заголовок (до 80 символов)
2. Напиши краткое описание на 2-3 предложения, которое заинтересует читателя
3. Используй эмодзи для привлечения внимания (но не переборщи)
4. Сохрани ключевую информацию из оригинала
5. Стиль: живой, современный, но информативный

ФОРМАТ ОТВЕТА (строго следуй формату):
Заголовок: [твой заголовок]
Описание: [твое описание]
Хештеги: [2-3 релевантных хештега через пробел]

Не добавляй ничего кроме указанного формата!"""

# Настройки логирования
LOG_LEVEL = 'INFO'
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
LOG_FILE = 'news_bot.log'

# Настройки Claude API
CLAUDE_MODEL = 'claude-3-5-sonnet-20241022'
CLAUDE_MAX_TOKENS = 500
CLAUDE_TEMPERATURE = 0.7
