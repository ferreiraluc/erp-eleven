import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import datetime

load_dotenv()

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eleven")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
    
    # Timezone configuration
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")  # GMT-3
    
    @property
    def tz(self):
        """Get timezone object"""
        return ZoneInfo(self.TIMEZONE)
    
    def now(self):
        """Get current time in configured timezone"""
        return datetime.now(self.tz)

settings = Settings()