"""
Веб-интерфейс Flask для мониторинга бота IDTrade
"""

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import json
from datetime import datetime
from typing import Dict, Optional


class BotWebInterface:
    """Класс веб-интерфейса для бота"""

    def __init__(self, bot_instance=None, host: str = '0.0.0.0', port: int = 5000, debug: bool = True):
        """
        Инициализация веб-интерфейса

        Args:
            bot_instance: Экземпляр бота
            host: Хост для запуска сервера
            port: Порт для запуска сервера
            debug: Режим отладки
        """
        self.app = Flask(__name__)
        self.app.config['SECRET_KEY'] = 'idtrade_secret_key_change_in_production'
        self.socketio = SocketIO(self.app, cors_allowed_origins="*")

        self.bot = bot_instance
        self.host = host
        self.port = port
        self.debug = debug

        self._setup_routes()
        self._setup_socketio()

    def _setup_routes(self):
        """Настройка маршрутов Flask"""

        @self.app.route('/')
        def index():
            """Главная страница"""
            return render_template('index.html')

        @self.app.route('/api/status')
        def get_status():
            """Получение статуса бота"""
            if self.bot:
                return jsonify(self.bot.get_status())
            return jsonify({
                'status': 'stopped',
                'message': 'Бот не запущен'
            })

        @self.app.route('/api/balance')
        def get_balance():
            """Получение баланса"""
            if self.bot:
                return jsonify(self.bot.get_balance())
            return jsonify({'error': 'Бот не запущен'})

        @self.app.route('/api/trades')
        def get_trades():
            """Получение истории сделок"""
            limit = request.args.get('limit', 50, type=int)
            symbol = request.args.get('symbol', None)

            if self.bot and self.bot.database:
                trades = self.bot.database.get_trades(symbol=symbol, limit=limit)
                return jsonify(trades)
            return jsonify([])

        @self.app.route('/api/signals')
        def get_signals():
            """Получение истории сигналов"""
            limit = request.args.get('limit', 50, type=int)
            symbol = request.args.get('symbol', None)

            if self.bot and self.bot.database:
                signals = self.bot.database.get_signals(symbol=symbol, limit=limit)
                return jsonify(signals)
            return jsonify([])

        @self.app.route('/api/stats')
        def get_stats():
            """Получение статистики"""
            symbol = request.args.get('symbol', None)

            if self.bot and self.bot.database:
                stats = self.bot.database.get_stats(symbol=symbol)
                return jsonify(stats)
            return jsonify({})

        @self.app.route('/api/config')
        def get_config():
            """Получение конфигурации бота"""
            if self.bot:
                return jsonify(self.bot.get_config())
            return jsonify({})

        @self.app.route('/api/start', methods=['POST'])
        def start_bot():
            """Запуск бота"""
            if self.bot:
                try:
                    # Здесь будет логика запуска бота
                    return jsonify({'success': True, 'message': 'Бот запущен'})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)})
            return jsonify({'success': False, 'error': 'Бот не инициализирован'})

        @self.app.route('/api/stop', methods=['POST'])
        def stop_bot():
            """Остановка бота"""
            if self.bot:
                try:
                    # Здесь будет логика остановки бота
                    return jsonify({'success': True, 'message': 'Бот остановлен'})
                except Exception as e:
                    return jsonify({'success': False, 'error': str(e)})
            return jsonify({'success': False, 'error': 'Бот не инициализирован'})

    def _setup_socketio(self):
        """Настройка WebSocket событий"""

        @self.socketio.on('connect')
        def handle_connect():
            """Обработка подключения клиента"""
            print(f'Клиент подключен: {request.sid}')
            emit('connection_response', {'status': 'connected'})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Обработка отключения клиента"""
            print(f'Клиент отключен: {request.sid}')

        @self.socketio.on('request_update')
        def handle_update_request():
            """Обработка запроса обновления данных"""
            if self.bot:
                emit('bot_update', self.bot.get_status())

    def emit_trade(self, trade_data: Dict):
        """
        Отправка информации о новой сделке всем клиентам

        Args:
            trade_data: Данные о сделке
        """
        self.socketio.emit('new_trade', trade_data)

    def emit_signal(self, signal_data: Dict):
        """
        Отправка информации о новом сигнале всем клиентам

        Args:
            signal_data: Данные о сигнале
        """
        self.socketio.emit('new_signal', signal_data)

    def emit_status_update(self, status_data: Dict):
        """
        Отправка обновления статуса всем клиентам

        Args:
            status_data: Данные статуса
        """
        self.socketio.emit('status_update', status_data)

    def run(self):
        """Запуск веб-сервера"""
        print(f"Запуск веб-интерфейса на http://{self.host}:{self.port}")
        self.socketio.run(self.app, host=self.host, port=self.port, debug=self.debug, allow_unsafe_werkzeug=True)


def create_app(bot_instance=None):
    """
    Фабрика для создания Flask приложения

    Args:
        bot_instance: Экземпляр бота

    Returns:
        BotWebInterface
    """
    return BotWebInterface(bot_instance)
