import os
from dotenv import load_dotenv
from zoneinfo import ZoneInfo
from datetime import datetime
from sqlalchemy.sql import func

load_dotenv()
load_dotenv("/etc/secrets/superfrete.env")
load_dotenv("/etc/secrets/openai.env")

class Settings:
    PRODUCTION: bool = os.getenv('RENDER', '').lower() == 'true' or os.getenv('APP_ENV', '').lower() == 'production'
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/eleven")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-change-this")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    DB_POOL_SIZE: int = int(os.getenv('DB_POOL_SIZE', '5'))
    DB_MAX_OVERFLOW: int = int(os.getenv('DB_MAX_OVERFLOW', '5'))
    DB_POOL_TIMEOUT: int = int(os.getenv('DB_POOL_TIMEOUT', '3'))
    DB_CONNECT_TIMEOUT: int = int(os.getenv('DB_CONNECT_TIMEOUT', '3'))
    DB_STATEMENT_TIMEOUT_MS: int = int(os.getenv('DB_STATEMENT_TIMEOUT_MS', '30000'))
    DB_LOCK_TIMEOUT_MS: int = int(os.getenv('DB_LOCK_TIMEOUT_MS', '10000'))
    # Leave idle transaction timeout opt-in: some existing provider workflows hold
    # transactions across network calls and must be separated before enforcing it.
    DB_IDLE_TRANSACTION_TIMEOUT_MS: int = int(os.getenv('DB_IDLE_TRANSACTION_TIMEOUT_MS', '0'))
    WONCA_API_KEY: str = os.getenv("WONCA_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    PRODUCT_PHOTO_IMAGE_MODEL: str = os.getenv("PRODUCT_PHOTO_IMAGE_MODEL", "gpt-image-1-mini")
    VISION_PROVIDER: str = os.getenv("VISION_PROVIDER", "auto").strip().lower()
    DEEPSEEK_VISION_MODEL: str = os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-flash")
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
    SUPERFRETE_WEBHOOK_SECRET: str = os.getenv('SUPERFRETE_WEBHOOK_SECRET', '')

    # Timezone configuration
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")  # GMT-3

    def validate_runtime(self):
        if self.ALGORITHM != 'HS256':
            raise RuntimeError('ALGORITHM deve ser HS256 para as sessões do ERP.')
        if self.PRODUCTION:
            if len(self.SECRET_KEY.encode()) < 32 or any(v in self.SECRET_KEY.lower() for v in ('change-this','replace-with','development-only')):
                raise RuntimeError('SECRET_KEY forte é obrigatória em produção; preserve a chave existente e seus dados cifrados.')
            if not self.DATABASE_URL.startswith(('postgresql://','postgresql+psycopg2://')):
                raise RuntimeError('PostgreSQL é obrigatório em produção.')
            if self.ASSISTANT_ENABLED and self.ASSISTANT_TELEGRAM_ENABLED and (not self.TELEGRAM_BOT_TOKEN or not self.TELEGRAM_WEBHOOK_SECRET):
                raise RuntimeError('Telegram ativo exige token e segredo de webhook.')
    
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
