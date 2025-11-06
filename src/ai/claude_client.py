"""
Клиент для Claude API - генерация уникального контента через AI.

Использует официальную библиотеку Anthropic для взаимодействия с Claude.
"""

import anthropic
from typing import Optional
from config import config
from ai.prompts import SYSTEM_PROMPT, format_prompt
from utils.logger import get_logger

logger = get_logger(__name__)


class ClaudeClient:
    """
    Клиент для генерации контента через Claude API.

    Features:
    - Асинхронная генерация контента
    - Настраиваемые параметры модели
    - Обработка ошибок и retry
    - Логирование всех запросов
    """

    def __init__(self):
        """Инициализирует Claude клиент."""
        self.client = anthropic.Anthropic(
            api_key=config.claude.api_key
        )
        self.model = config.claude.model
        self.max_tokens = config.claude.max_tokens
        self.temperature = config.claude.temperature

    async def generate_content(
        self,
        prompt_template: str,
        data: dict,
        max_retries: int = 2
    ) -> Optional[str]:
        """
        Генерирует уникальный контент для события через Claude API.

        Args:
            prompt_template: Шаблон промпта для события
            data: Данные события для подстановки
            max_retries: Количество попыток при ошибке

        Returns:
            str или None: Сгенерированный текст или None при ошибке

        Example:
            >>> client = ClaudeClient()
            >>> data = {'amount_usd': 5000000, 'symbol': 'BTC', ...}
            >>> message = await client.generate_content(WHALE_ALERT_PROMPT, data)
            >>> len(message) > 0
            True
        """
        # Форматируем промпт с данными
        user_prompt = format_prompt(prompt_template, data)

        for attempt in range(max_retries):
            try:
                logger.debug(f"Запрос к Claude API (попытка {attempt + 1}/{max_retries})")

                # Вызываем Claude API
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature,
                    system=SYSTEM_PROMPT,
                    messages=[
                        {"role": "user", "content": user_prompt}
                    ]
                )

                # Извлекаем текст из ответа
                generated_text = message.content[0].text

                logger.info(f"✅ Claude API: успешно сгенерирован контент ({len(generated_text)} символов)")

                return generated_text

            except anthropic.APIError as e:
                logger.error(f"Claude API ошибка: {e}")
                if attempt < max_retries - 1:
                    logger.info("Повторная попытка...")
                    continue
                else:
                    logger.error("❌ Не удалось сгенерировать контент через Claude API")
                    return None

            except Exception as e:
                logger.error(f"Неожиданная ошибка при генерации: {e}", exc_info=True)
                return None

        return None

    def estimate_cost(self, input_tokens: int, output_tokens: int) -> float:
        """
        Оценивает стоимость запроса к Claude API.

        Args:
            input_tokens: Количество входных токенов
            output_tokens: Количество выходных токенов

        Returns:
            float: Стоимость в USD

        Example:
            >>> client = ClaudeClient()
            >>> cost = client.estimate_cost(400, 600)
            >>> cost < 0.02
            True
        """
        # Цены для Claude Sonnet 4 (апрель 2025)
        INPUT_PRICE = 3.0 / 1_000_000  # $3 per 1M tokens
        OUTPUT_PRICE = 15.0 / 1_000_000  # $15 per 1M tokens

        input_cost = input_tokens * INPUT_PRICE
        output_cost = output_tokens * OUTPUT_PRICE

        total = input_cost + output_cost
        return round(total, 6)

    def get_usage_stats(self) -> dict:
        """
        Возвращает статистику использования API.

        Returns:
            dict: Статистика использования
        """
        # TODO: Реализовать отслеживание использования
        # Можно добавить подсчет токенов и стоимости
        return {
            'model': self.model,
            'max_tokens': self.max_tokens,
            'temperature': self.temperature,
        }


# Глобальный экземпляр для использования в приложении
claude_client = ClaudeClient()
