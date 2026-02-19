"""
АКТИВНЫЙ ПИНГ - КАЖДУЮ МИНУТУ
"""

import threading
import time
import requests
import logging
from config import RENDER_URL

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
        logger.info("🔥 АКТИВНЫЙ ПИНГ: каждую минуту!")
    
    def _ping_worker(self):
        time.sleep(30)  # Короткая задержка перед стартом
        url = f"{RENDER_URL.rstrip('/')}/ping"
        
        while self.running:
            self.ping_count += 1
            try:
                response = requests.get(url, timeout=5)
                logger.info(f"⚡ Пинг #{self.ping_count}: {response.status_code}")
            except Exception as e:
                logger.debug(f"Пинг #{self.ping_count}: {e}")
            
            # Пинг КАЖДУЮ МИНУТУ (60 секунд)
            time.sleep(60)

ping_service = PingService()
