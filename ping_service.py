"""
ПРОСТОЙ АВТО-ПИНГ
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
    
    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._ping_worker, daemon=True)
        self.thread.start()
        logger.info("✅ Автопинг запущен (3 минуты)")
    
    def _ping_worker(self):
        time.sleep(60)
        url = f"{RENDER_URL.rstrip('/')}/ping"
        while self.running:
            try:
                requests.get(url, timeout=5)
            except:
                pass
            time.sleep(180)

ping_service = PingService()
