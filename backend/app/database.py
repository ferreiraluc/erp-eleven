from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.engine import make_url
from .config import settings

def engine_options(url):
    options = {'pool_pre_ping': True, 'hide_parameters': True}
    if make_url(url).get_backend_name() == 'postgresql':
        options.update(pool_size=settings.DB_POOL_SIZE, max_overflow=settings.DB_MAX_OVERFLOW,
                       pool_timeout=settings.DB_POOL_TIMEOUT, pool_recycle=900,
                       connect_args={'connect_timeout': settings.DB_CONNECT_TIMEOUT,
                           'application_name': 'erp-eleven',
                           'options': f'-c statement_timeout={settings.DB_STATEMENT_TIMEOUT_MS} '
                                      f'-c lock_timeout={settings.DB_LOCK_TIMEOUT_MS} '
                                      f'-c idle_in_transaction_session_timeout={settings.DB_IDLE_TRANSACTION_TIMEOUT_MS}'})
        if settings.PRODUCTION:
            # Render internal endpoints support TLS but use a self-signed cert.
            # Preserve a stricter configured mode; never fall back to plaintext.
            mode = make_url(url).query.get('sslmode')
            options['connect_args']['sslmode'] = mode if mode in ('require', 'verify-ca', 'verify-full') else 'require'
    return options

engine = create_engine(settings.DATABASE_URL, **engine_options(settings.DATABASE_URL))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, info={"audit_enabled": True})

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
