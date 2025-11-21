FROM python:3.11-slim

WORKDIR /app

# Системные зависимости (минимум)
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY bot ./bot

# Непривилегированный пользователь
RUN useradd -m -u 1000 botuser && \
    chown -R botuser:botuser /app
USER botuser

# Healthcheck
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import asyncio; print('healthy')" || exit 1

# Запуск
CMD ["python", "-m", "bot.main"]
