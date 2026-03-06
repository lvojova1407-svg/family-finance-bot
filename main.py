"""
АКТИВНЫЙ ПИНГ - КАЖДУЮ МИНУТУ
Сервис для предотвращения отключения на Render
"""

import threading
import time
import requests
import logging
import os

logger = logging.getLogger(__name__)

class PingService:
    def __init__(self):
        self.running = False
        self.thread = None
        self.ping_count = 0
        self.url = None
    
    def start(self):
        """Запускает сервис пинга"""
        if self.running:
            logger.warning("⚠️ Пинг уже запущен")
            return
        
        # Определяем URL для пинга
        render_url = os.getenv("RENDER_URL", "").rstrip('/')
        if render_url:
            self.url = f"{render_url}/health"
        else:
            # Пробуем сгенерировать URL
            try:
                import socket
                hostname = socket.gethostname()
                self.url = f"https://{hostname}.onrender.com/health"
            except:
                port = os.getenv("PORT", 10000)
                self.url = f"http://localhost:{port}/health"
                logger.warning(f"⚠️ Использую localhost: {self.url}")
        
        self.running = True
        self.thread = threading.Thread(target=self._ping_worker, daemon=True)
        self.thread.start()
        logger.info(f"🔥 АКТИВНЫЙ ПИНГ ЗАПУЩЕН: {self.url} (каждую минуту)")
    
    def stop(self):
        """Останавливает сервис пинга"""
        self.running = False
        logger.info("⏹️ Пинг остановлен")
    
    def _ping_worker(self):
        """Рабочий поток для пинга"""
        time.sleep(30)  # Задержка перед стартом
        
        while self.running:
            self.ping_count += 1
            try:
                response = requests.get(
                    self.url, 
                    timeout=10,
                    headers={"User-Agent": "Render-PingService/1.0"}
                )
                if response.status_code == 200:
                    logger.info(f"⚡ Пинг #{self.ping_count}: ✅ {response.status_code}")
                else:
                    logger.warning(f"⚡ Пинг #{self.ping_count}: ⚠️ {response.status_code}")
            except Exception as e:
                logger.debug(f"⚡ Пинг #{self.ping_count}: ❌ {str(e)[:50]}")
            
            # Пинг КАЖДУЮ МИНУТУ (60 секунд)
            # Render считает сервис активным при запросах раз в 5-10 минут
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1)

# Создаем глобальный экземпляр
ping_service = PingService()
