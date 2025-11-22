"""
Конфигурация источников новостей
"""

# RSS каналы для сбора российских новостей
RUSSIAN_RSS_FEEDS = {
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

# RSS каналы для сбора международных новостей (европейские и американские)
INTERNATIONAL_RSS_FEEDS = {
    'Reuters': 'https://www.reuters.com/rssFeed/worldNews',
    'BBC News': 'https://feeds.bbci.co.uk/news/world/rss.xml',
    'CNN': 'http://rss.cnn.com/rss/edition_world.rss',
    'The Guardian': 'https://www.theguardian.com/world/rss',
    'The New York Times': 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
    'Financial Times': 'https://www.ft.com/world?format=rss',
    'Le Monde': 'https://www.lemonde.fr/international/rss_full.xml',
    'Der Spiegel': 'https://www.spiegel.de/international/index.rss',
    'Politico': 'https://www.politico.eu/feed/',
    'Euronews': 'https://www.euronews.com/rss'
}

# Объединенный список всех RSS каналов (для совместимости со старым кодом)
RSS_FEEDS = {**RUSSIAN_RSS_FEEDS, **INTERNATIONAL_RSS_FEEDS}

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

# Ключевые слова для фильтрации международных новостей о России
RUSSIA_RELATED_KEYWORDS = [
    'russia',
    'russian',
    'moscow',
    'kremlin',
    'putin',
    'россия',
    'российск',
    'москва',
    'кремль',
    'путин'
]
