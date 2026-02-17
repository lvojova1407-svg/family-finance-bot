"""
СЕРВИС АВТО-ПИНГА ДЛЯ RENDER
Предотвращает "засыпание" бота на бесплатном тарифе
"""

import threading
import time
import requests
import logging
from config import RENDER_URL

logger = logging.getLogger(__name__)

class PingService:
    """Сервис для автоматического пинга бота"""
    
    def __init__(self, ping_interval=480):  # 8 минут
        self.ping_interval = ping_interval
        self.running = False
        self.thread = None
    
    def start(self):
        """Запускает сервис пинга в отдельном потоке"""
        if self.running:
            logger.warning("⚠️ Сервис пинга уже запущен")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._ping_worker, daemon=True)
        self.thread.start()
        logger.info(f"✅ Сервис пинга запущен (интервал: {self.ping_interval}с)")
    
    def stop(self):
        """Останавливает сервис пинга"""
        self.running = False
        logger.info("🛑 Сервис пинга остановлен")
    
    def _ping_worker(self):
        """Рабочий поток для пинга"""
        # Даем время на полный запуск бота
        time.sleep(30)
        
        ping_count = 0
        health_url = f"{RENDER_URL}/health"
        
        logger.info(f"🧵 Поток пинга запущен для {health_url}")
        
        while self.running:
            ping_count += 1
            try:
                response = requests.get(health_url, timeout=10)
                
                if response.status_code == 200:
                    logger.info(f"✅ Пинг #{ping_count} успешен")
                else:
                    logger.warning(f"⚠️ Пинг #{ping_count}: код {response.status_code}")
                    
            except requests.exceptions.ConnectionError:
                logger.warning(f"⚠️ Пинг #{ping_count}: сервер еще не готов")
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Пинг #{ping_count}: таймаут")
            except Exception as e:
                logger.error(f"❌ Ошибка пинга #{ping_count}: {e}")
            
            # Ждем следующий пинг
            for _ in range(self.ping_interval):
                if not self.running:
                    break
                time.sleep(1)


# Глобальный экземпляр сервиса пинга
ping_service = PingService()
