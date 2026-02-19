"""
ПРОСТОЙ АВТО-ПИНГ ДЛЯ RENDER
Пинг каждые 180 секунд (3 минуты)
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
        logger.info(f"✅ Автопинг запущен (интервал: {PING_INTERVAL}с / {PING_INTERVAL//60} минут)")
    
    def _ping_worker(self):
        """Рабочий поток"""
        time.sleep(60)  # Задержка перед первым пингом
        
        base_url = RENDER_URL.rstrip('/')
        logger.info(f"🧵 Поток пинга запущен для {base_url}")
        
        while self.running:
            self.ping_count += 1
            
            try:
                response = requests.get(base_url, timeout=30)
                
                if response.status_code in [200, 405]:
                    logger.info(f"✅ Пинг #{self.ping_count} - ответ {response.status_code}")
                else:
                    logger.warning(f"⚠️ Пинг #{self.ping_count} - код {response.status_code}")
                    
            except Exception as e:
                logger.debug(f"Пинг #{self.ping_count} - {e}")
            
            time.sleep(PING_INTERVAL)


# Глобальный экземпляр
ping_service = PingService()
