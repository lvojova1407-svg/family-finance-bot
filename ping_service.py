"""
ПРОСТОЙ АВТО-ПИНГ ДЛЯ RENDER
Пинг каждые 5 минут
"""

import threading
import time
import requests
import logging
from config import RENDER_URL, PING_INTERVAL

logger = logging.getLogger(__name__)

class PingService:
    """Сервис автоматического пинга каждые 5 минут"""
    
    def __init__(self):
        self.running = False
        self.thread = None
        self.ping_count = 0
    
    def start(self):
        """Запускает сервис пинга"""
        if self.running:
            logger.warning("⚠️ Пинг уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._ping_worker, daemon=True)
        self.thread.start()
        logger.info(f"✅ Автопинг запущен (интервал: {PING_INTERVAL}с / 5 минут)")
    
    def stop(self):
        """Останавливает сервис пинга"""
        self.running = False
        logger.info("🛑 Автопинг остановлен")
    
    def _ping_worker(self):
        """Рабочий поток"""
        # Даем время на полный запуск бота
        time.sleep(30)
        
        # Пингуем разные эндпоинты для надежности
        endpoints = ["/ping", "/health", "/"]
        
        logger.info(f"🧵 Поток пинга запущен для {RENDER_URL}")
        
        while self.running:
            self.ping_count += 1
            
            # Пробуем разные эндпоинты по очереди
            for endpoint in endpoints:
                try:
                    url = f"{RENDER_URL}{endpoint}"
                    response = requests.get(url, timeout=10)
                    
                    if response.status_code == 200:
                        logger.info(f"✅ Пинг #{self.ping_count} - {endpoint} - {response.status_code}")
                        break  # Успешно, выходим из цикла эндпоинтов
                    else:
                        logger.warning(f"⚠️ Пинг #{self.ping_count} - {endpoint} - код {response.status_code}")
                        
                except requests.exceptions.ConnectionError:
                    logger.warning(f"⚠️ Пинг #{self.ping_count} - {endpoint} - сервер еще не готов")
                except requests.exceptions.Timeout:
                    logger.warning(f"⚠️ Пинг #{self.ping_count} - {endpoint} - таймаут")
                except Exception as e:
                    logger.error(f"❌ Пинг #{self.ping_count} - {endpoint} - ошибка: {e}")
            
            # Ждем следующий пинг (5 минут)
            for _ in range(PING_INTERVAL):
                if not self.running:
                    break
                time.sleep(1)


# Глобальный экземпляр сервиса пинга
ping_service = PingService()
