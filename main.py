#!/usr/bin/env python3
"""
IDTrade - Криптовалютный торговый бот
Главная точка входа

Использование:
    python main.py                  # Запуск с веб-интерфейсом
    python main.py --no-web         # Запуск без веб-интерфейса
    python main.py --config path    # Запуск с кастомным конфигом
"""

import asyncio
import argparse
import sys
import signal
import threading
from pathlib import Path

# Добавление корневой директории в path
sys.path.insert(0, str(Path(__file__).parent))

from bot.core.trading_bot import TradingBot
from bot.web.app import BotWebInterface


class IDTradeApp:
    """Главное приложение IDTrade"""

    def __init__(self, config_path: str = "bot/config/config.yaml", enable_web: bool = True):
        """
        Инициализация приложения

        Args:
            config_path: Путь к конфигурационному файлу
            enable_web: Включить веб-интерфейс
        """
        self.config_path = config_path
        self.enable_web = enable_web
        self.bot = None
        self.web_interface = None
        self.bot_loop = None
        self.bot_task = None

    def setup_signal_handlers(self):
        """Настройка обработчиков сигналов для graceful shutdown"""
        def signal_handler(sig, frame):
            print("\n\nПолучен сигнал остановки...")
            self.shutdown()
            sys.exit(0)

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    def start_bot_in_background(self):
        """Запуск бота в фоновом потоке"""
        def run_bot():
            self.bot_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.bot_loop)
            self.bot_task = self.bot_loop.create_task(self.bot.run())
            try:
                self.bot_loop.run_until_complete(self.bot_task)
            except asyncio.CancelledError:
                print("Бот остановлен")
            finally:
                self.bot_loop.close()

        bot_thread = threading.Thread(target=run_bot, daemon=True)
        bot_thread.start()
        print("Бот запущен в фоновом режиме")

    def run(self):
        """Запуск приложения"""
        print("=" * 60)
        print("IDTrade - Криптовалютный торговый бот")
        print("=" * 60)
        print()

        # Настройка обработчиков сигналов
        self.setup_signal_handlers()

        # Инициализация бота
        print(f"Загрузка конфигурации из: {self.config_path}")
        self.bot = TradingBot(config_path=self.config_path)
        print(f"Режим работы: {self.bot.config['trading']['mode'].upper()}")
        print(f"Торговые пары: {', '.join(self.bot.config['trading']['pairs'])}")
        print(f"Стратегия: {self.bot.strategy.name}")
        print()

        if self.enable_web:
            print("Запуск с веб-интерфейсом...")
            print()

            # Запуск бота в фоновом режиме
            self.start_bot_in_background()

            # Инициализация веб-интерфейса
            web_config = self.bot.config.get('web', {})
            self.web_interface = BotWebInterface(
                bot_instance=self.bot,
                host=web_config.get('host', '0.0.0.0'),
                port=web_config.get('port', 5000),
                debug=web_config.get('debug', True)
            )

            # Запуск веб-сервера (блокирующий вызов)
            self.web_interface.run()

        else:
            print("Запуск без веб-интерфейса...")
            print("Для остановки нажмите Ctrl+C")
            print()

            # Запуск бота напрямую
            try:
                asyncio.run(self.bot.run())
            except KeyboardInterrupt:
                print("\n\nОстановка бота...")
                self.shutdown()

    def shutdown(self):
        """Корректное завершение работы"""
        print("Завершение работы приложения...")

        if self.bot:
            self.bot.stop()

        if self.bot_task and not self.bot_task.done():
            self.bot_task.cancel()

        if self.bot_loop and self.bot_loop.is_running():
            self.bot_loop.stop()

        print("Приложение остановлено")


def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(
        description='IDTrade - Криптовалютный торговый бот',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python main.py                          # Запуск с веб-интерфейсом
  python main.py --no-web                 # Запуск без веб-интерфейса
  python main.py --config custom.yaml     # Использование кастомного конфига
        """
    )

    parser.add_argument(
        '--config',
        type=str,
        default='bot/config/config.yaml',
        help='Путь к конфигурационному файлу (по умолчанию: bot/config/config.yaml)'
    )

    parser.add_argument(
        '--no-web',
        action='store_true',
        help='Запустить без веб-интерфейса'
    )

    parser.add_argument(
        '--version',
        action='version',
        version='IDTrade v1.0.0'
    )

    args = parser.parse_args()

    # Запуск приложения
    app = IDTradeApp(
        config_path=args.config,
        enable_web=not args.no_web
    )

    try:
        app.run()
    except Exception as e:
        print(f"\nКритическая ошибка: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
