"""
Планировщик задач - управляет расписанием сбора данных и публикаций.

Использует APScheduler для запуска задач по расписанию.
"""

import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from utils.logger import get_logger
from config import config

logger = get_logger(__name__)


class TaskScheduler:
    """
    Управляет расписанием всех задач бота.

    Задачи:
    - Сбор рыночных данных
    - Проверка индекса страха/жадности
    - Рыночные обзоры в фиксированное время
    - Очистка старых данных
    """

    def __init__(
        self,
        market_collector,
        fear_greed_collector,
        message_queue,
        importance_scorer,
        content_generator
    ):
        """
        Инициализирует планировщик.

        Args:
            market_collector: Коллектор рыночных данных
            fear_greed_collector: Коллектор индекса страха/жадности
            message_queue: Очередь сообщений
            importance_scorer: Оценщик важности
            content_generator: Генератор контента
        """
        self.scheduler = AsyncIOScheduler()
        self.market_collector = market_collector
        self.fear_greed_collector = fear_greed_collector
        self.queue = message_queue
        self.scorer = importance_scorer
        self.generator = content_generator

        logger.info("TaskScheduler инициализирован")

    def start(self):
        """Запускает планировщик и регистрирует все задачи."""
        logger.info("🚀 Запуск планировщика задач...")

        # Проверка очереди каждую минуту
        self.scheduler.add_job(
            self.queue.process_queue_periodically,
            trigger=IntervalTrigger(minutes=1),
            id='queue_processor',
            name='Обработка очереди сообщений',
            replace_existing=True
        )

        # Рыночные обзоры в фиксированное время
        for time_str in config.schedule.market_overview_times:
            hour, minute = map(int, time_str.split(':'))

            self.scheduler.add_job(
                self.generate_market_overview,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=f'market_overview_{time_str}',
                name=f'Рыночный обзор {time_str} UTC',
                replace_existing=True
            )
            logger.info(f"📊 Запланирован рыночный обзор на {time_str} UTC")

        # Проверка индекса страха/жадности
        self.scheduler.add_job(
            self.check_fear_greed_index,
            trigger=IntervalTrigger(minutes=config.schedule.fear_greed_check_interval),
            id='fear_greed_check',
            name='Проверка индекса страха/жадности',
            replace_existing=True
        )

        # Очистка старых записей в БД (раз в день в 3:00 UTC)
        self.scheduler.add_job(
            self.cleanup_old_data,
            trigger=CronTrigger(hour=3, minute=0),
            id='cleanup_old_data',
            name='Очистка старых данных',
            replace_existing=True
        )

        # Очистка старых сообщений в очереди (каждые 6 часов)
        self.scheduler.add_job(
            self.queue.clear_old_messages,
            trigger=IntervalTrigger(hours=6),
            id='clear_old_queue',
            name='Очистка старых сообщений в очереди',
            replace_existing=True
        )

        # Запускаем планировщик
        self.scheduler.start()
        logger.info("✅ Планировщик запущен успешно")

        # Логируем все запланированные задачи
        self.log_scheduled_jobs()

    def stop(self):
        """Останавливает планировщик."""
        logger.info("Остановка планировщика...")
        self.scheduler.shutdown(wait=True)
        logger.info("✅ Планировщик остановлен")

    async def generate_market_overview(self):
        """
        Генерирует и публикует рыночный обзор.

        Запускается по расписанию (утром и вечером).
        """
        logger.info("📊 Генерация рыночного обзора...")

        try:
            # Собираем рыночные данные
            top_coins = await self.market_collector.get_top_coins(limit=100)
            global_stats = await self.market_collector.get_global_stats()
            gainers_losers = await self.market_collector.get_top_gainers_losers(limit=5)
            fear_greed = await self.fear_greed_collector.get_current_index()

            # Определяем период (утро/вечер)
            current_hour = datetime.utcnow().hour
            period = "утренний" if current_hour < 12 else "вечерний"

            # Подготавливаем данные для промпта
            # Находим BTC и ETH
            btc = next((c for c in top_coins if c['symbol'] == 'BTC'), None)
            eth = next((c for c in top_coins if c['symbol'] == 'ETH'), None)

            data = {
                'period': period,
                'gainers_data': self._format_coins_list(gainers_losers['gainers']),
                'losers_data': self._format_coins_list(gainers_losers['losers']),
                'btc_price': btc['current_price'] if btc else 0,
                'btc_change': btc['price_change_24h'] if btc else 0,
                'eth_price': eth['current_price'] if eth else 0,
                'eth_change': eth['price_change_24h'] if eth else 0,
                'total_mcap': global_stats['total_market_cap'] if global_stats else 0,
                'btc_dominance': global_stats['btc_dominance'] if global_stats else 0,
                'fear_greed': f"{fear_greed['value']} ({fear_greed['classification']})" if fear_greed else "N/A",
            }

            # Генерируем контент через AI
            message = await self.generator.generate_market_overview(data)

            if message:
                # Оценка важности (рыночные обзоры всегда важны)
                importance = self.scorer.score_market_overview()

                # Добавляем в очередь
                event_hash = self.queue.db.generate_event_hash(
                    'market_overview',
                    {'date': datetime.utcnow().strftime('%Y-%m-%d'), 'time': period}
                )

                await self.queue.add_message(
                    message_text=message,
                    importance_score=importance,
                    event_type='market_overview',
                    event_hash=event_hash
                )

            logger.info("✅ Рыночный обзор сгенерирован и добавлен в очередь")

        except Exception as e:
            logger.error(f"❌ Ошибка генерации рыночного обзора: {e}", exc_info=True)

    async def check_fear_greed_index(self):
        """
        Проверяет индекс страха/жадности и публикует если есть значимые изменения.
        """
        logger.debug("🔍 Проверка индекса страха/жадности...")

        try:
            current = await self.fear_greed_collector.get_current_index()

            if not current:
                return

            current_value = current['value']
            previous_value = self.queue.db.get_last_fear_greed_value()

            # Сохраняем текущее значение
            self.queue.db.save_fear_greed_index(
                value=current_value,
                classification=current['classification']
            )

            # Если нет предыдущего значения, просто сохраняем
            if previous_value is None:
                logger.debug(f"Индекс страха/жадности: {current_value} (первая запись)")
                return

            # Оцениваем важность изменения
            importance = self.scorer.score_fear_greed_change(current_value, previous_value)

            # Публикуем только если важность >= порога
            if importance >= config.filters.min_importance_score:
                logger.info(f"📈 Значимое изменение индекса: {previous_value} → {current_value}")

                # Генерируем контент
                # TODO: Добавить генерацию через AI
                # Пока используем простой шаблон

                message = f"""
📊 **ИНДЕКС СТРАХА И ЖАДНОСТИ**

Текущее значение: **{current_value}/100** ({current['classification']})
Изменение: {current_value - previous_value:+d} пунктов

Предыдущее значение: {previous_value}/100

━━━━━━━━━━━━━━━━━━━━
⚠️ Не является финансовым советом. Информация в ознакомительных целях.
"""

                event_hash = self.queue.db.generate_event_hash(
                    'fear_greed',
                    {'value': current_value, 'previous': previous_value}
                )

                await self.queue.add_message(
                    message_text=message,
                    importance_score=importance,
                    event_type='fear_greed',
                    event_hash=event_hash
                )

        except Exception as e:
            logger.error(f"❌ Ошибка проверки индекса: {e}", exc_info=True)

    async def cleanup_old_data(self):
        """Очищает старые записи из БД."""
        logger.info("🗑️ Очистка старых данных...")
        try:
            self.queue.db.cleanup_old_records(days=30)
            logger.info("✅ Старые данные очищены")
        except Exception as e:
            logger.error(f"Ошибка очистки данных: {e}", exc_info=True)

    def log_scheduled_jobs(self):
        """Выводит список запланированных задач."""
        logger.info("\n" + "=" * 60)
        logger.info("📅 ЗАПЛАНИРОВАННЫЕ ЗАДАЧИ:")
        logger.info("=" * 60)

        jobs = self.scheduler.get_jobs()
        for job in jobs:
            logger.info(f"  • {job.name}")
            logger.info(f"    ID: {job.id}")
            logger.info(f"    След. запуск: {job.next_run_time}")

        logger.info("=" * 60 + "\n")

    def _format_coins_list(self, coins: list) -> str:
        """
        Форматирует список монет для промпта.

        Args:
            coins: Список монет

        Returns:
            str: Отформатированный список
        """
        result = []
        for i, coin in enumerate(coins, 1):
            result.append(
                f"{i}. {coin['name']} ({coin['symbol']}): "
                f"${coin['current_price']:.2f} ({coin['price_change_24h']:+.2f}%)"
            )
        return "\n".join(result)
