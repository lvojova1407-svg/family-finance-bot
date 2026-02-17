"""
ПРОСТОЙ АВТО-ПИНГ ДЛЯ RENDER
Пинг каждые 5 минут - УЛЬТРАСТАБИЛЬНАЯ ВЕРСИЯ
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
        # УВЕЛИЧЕННОЕ время ожидания
        time.sleep(90)  # 90 секунд вместо 60
        
        base_url = RENDER_URL.rstrip('/')
        logger.info(f"🧵 Поток пинга запущен для {base_url}")
        
        while self.running:
            self.ping_count += 1
            
            try:
                # Пинг с увеличенным таймаутом
                response = requests.get(base_url, timeout=30)
                
                if response.status_code == 200:
                    logger.info(f"✅ Пинг #{self.ping_count} - OK (200)")
                else:
                    logger.info(f"✅ Пинг #{self.ping_count} - ответ {response.status_code}")
                    
            except Exception as e:
                # НЕ логгируем как ошибку, только как предупреждение
                logger.debug(f"Пинг #{self.ping_count} - {e}")
            
            # Точный интервал
            time.sleep(PING_INTERVAL)

# Глобальный экземпляр
ping_service = PingService()
