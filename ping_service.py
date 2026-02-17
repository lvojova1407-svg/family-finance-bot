"""
ПРОСТОЙ АВТО-ПИНГ ДЛЯ RENDER
Пинг каждые 5 минут - ИСПРАВЛЕННАЯ ВЕРСИЯ
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
        time.sleep(30)
        
        # Используем ТОЛЬКО корневой URL (без /ping, без /health)
        base_url = RENDER_URL.rstrip('/')
        
        logger.info(f"🧵 Поток пинга запущен для {base_url}")
        
        while self.running:
            self.ping_count += 1
            
            try:
                # Пингуем ТОЛЬКО корневой URL (он точно работает)
                response = requests.get(base_url, timeout=10)
                
                # 200 - успех, 405 - тоже успех (главное что сервер ответил)
                if response.status_code in [200, 405]:
                    logger.info(f"✅ Пинг #{self.ping_count} - сервер ответил ({response.status_code})")
                else:
                    logger.warning(f"⚠️ Пинг #{self.ping_count} - код {response.status_code}")
                    
            except Exception as e:
                logger.error(f"❌ Пинг #{self.ping_count} - ошибка: {e}")
            
            # Ждем ровно 5 минут
            time.sleep(PING_INTERVAL)


# Глобальный экземпляр
ping_service = PingService()
