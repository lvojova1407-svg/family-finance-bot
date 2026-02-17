"""
ПРОСТОЙ АВТО-ПИНГ ДЛЯ RENDER
С задержкой перед первым пингом
"""

import threading
import time
import requests
import logging
from config import RENDER_URL, PING_INTERVAL

logger = logging.getLogger(__name__)

class PingService:
    def __init__(self):
        self.running = False
        self.thread = None
        self.ping_count = 0
    
    def start(self):
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._ping_worker, daemon=True)
        self.thread.start()
        logger.info(f"✅ Автопинг запущен (интервал: {PING_INTERVAL}с / 5 минут)")
    
    def _ping_worker(self):
        """Рабочий поток"""
        # Даем серверу время полностью запуститься
        logger.info("⏳ Ожидание 60 секунд перед первым пингом...")
        time.sleep(60)
        
        base_url = RENDER_URL.rstrip('/')
        logger.info(f"🧵 Поток пинга запущен для {base_url}")
        
        while self.running:
            self.ping_count += 1
            
            try:
                # Увеличиваем таймаут до 30 секунд
                response = requests.get(base_url, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"✅ Пинг #{self.ping_count} - успешно (200)")
                else:
                    logger.info(f"✅ Пинг #{self.ping_count} - сервер ответил ({response.status_code})")
                    
            except requests.exceptions.Timeout:
                logger.warning(f"⚠️ Пинг #{self.ping_count} - таймаут, но сервер возможно загружен")
                # Не считаем это критической ошибкой
            except Exception as e:
                logger.error(f"❌ Пинг #{self.ping_count} - ошибка: {e}")
            
            # Ждем следующий пинг
            time.sleep(PING_INTERVAL)


# Глобальный экземпляр
ping_service = PingService()
