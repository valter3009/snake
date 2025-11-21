# Используем официальный Python образ (легкий и быстрый)
FROM python:3.11-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем requirements.txt
COPY requirements.txt .

# Устанавливаем зависимости (один слой для кеширования)
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY bot ./bot

# Запускаем бота
CMD ["python", "-m", "bot.main"]
