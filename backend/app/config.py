import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy.sql import func

load_dotenv()
load_dotenv("/etc/secrets/superfrete.env")

class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eleven")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080"))  # legacy fallback; real expiry is midnight+7d
    WONCA_API_KEY: str = os.getenv("WONCA_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ASSISTANT_ENABLED: bool = os.getenv("ASSISTANT_ENABLED", "false").lower() == "true"
    ASSISTANT_TELEGRAM_ENABLED: bool = os.getenv("ASSISTANT_TELEGRAM_ENABLED", "true").lower() == "true"
    ASSISTANT_WHATSAPP_ENABLED: bool = os.getenv("ASSISTANT_WHATSAPP_ENABLED", "false").lower() == "true"
    ASSISTANT_EMBEDDED_WORKER: bool = os.getenv("ASSISTANT_EMBEDDED_WORKER", "false").lower() == "true"
    ASSISTANT_DAILY_MESSAGES: int = int(os.getenv("ASSISTANT_DAILY_MESSAGES", "100"))
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-flash")
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM: str = os.getenv("TWILIO_WHATSAPP_FROM", "")
    TWILIO_WEBHOOK_URL: str = os.getenv("TWILIO_WEBHOOK_URL", "")
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", "")
    TELEGRAM_BOT_USERNAME: str = os.getenv("TELEGRAM_BOT_USERNAME", "").lstrip("@")
    TELEGRAM_GROUP_ID: str = os.getenv("TELEGRAM_GROUP_ID", "")
    
    SUPERFRETE_TOKEN: str = os.getenv('SUPERFRETE_TOKEN', '')
    SUPERFRETE_CONTACT_EMAIL: str = os.getenv('SUPERFRETE_CONTACT_EMAIL', '')
    SUPERFRETE_SANDBOX: bool = os.getenv('SUPERFRETE_SANDBOX', 'true').lower() == 'true'

    # Timezone configuration
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")  # GMT-3
    
    @property
    def tz(self):
        """Get timezone object"""
        return ZoneInfo(self.TIMEZONE)
    
    def now(self):
        """Get current time in configured timezone"""
        return datetime.now(self.tz)
    
    def get_timezone_aware_timestamp(self):
        """Get current timestamp with timezone for database"""
        return func.timezone(self.TIMEZONE, func.current_timestamp())

settings = Settings()
