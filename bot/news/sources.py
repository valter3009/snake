"""
Конфигурация источников новостей
"""

# RSS каналы для сбора новостей
RSS_FEEDS = {
    'РБК': 'https://rssexport.rbc.ru/rbcnews/news/30/full.rss',
    'ТАСС': 'https://tass.ru/rss/v2.html',
    'Коммерсантъ': 'https://www.kommersant.ru/RSS/main.xml',
    'Ведомости': 'https://www.vedomosti.ru/rss/news',
    'Медуза': 'https://meduza.io/rss/all',
    'РИА Новости': 'https://ria.ru/export/rss2/archive/index.xml',
    'Интерфакс': 'https://www.interfax.ru/rss.asp',
    'Газета.ру': 'https://www.gazeta.ru/export/rss/lenta.xml',
    'Lenta.ru': 'https://lenta.ru/rss/news',
    'RT': 'https://russian.rt.com/rss',
    'BBC Russian': 'https://feeds.bbci.co.uk/russian/rss.xml'
}

# NewsAPI категории для поиска
NEWSAPI_SOURCES = [
    'lenta',
    'rbc',
    'tass'
]

# Ключевые слова для фильтрации российских политических новостей
KEYWORDS = [
    'россия',
    'москва',
    'кремль',
    'путин',
    'правительство',
    'дума',
    'выборы',
    'политика',
    'санкции',
    'экономика',
    'геополитика'
]
