from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import traceback
import logging
import sys
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .api.endpoints import vendas, vendedores, cambistas, auth, pedidos, dashboard, exchange_rates, money_transfers, rastreamento, excel_import, tags, inventory, clientes
from .logging_config import setup_logging, get_logger
from .database import engine, Base

# Main
# Setup logging
import os
log_level = os.getenv("LOG_LEVEL", "INFO")  # Default to INFO for better tracking
setup_logging(level=log_level)
logger = get_logger(__name__)

def _job_atualizar_rastreamentos():
    """Scheduled job: update all active (non-delivered) trackings via Wonca API."""
    from .database import SessionLocal
    from .models.rastreamento import Rastreamento, RastreamentoStatus
    from .services.wonca_service import parse_tracking
    from datetime import datetime

    db = SessionLocal()
    try:
        ativos = db.query(Rastreamento).filter(
            Rastreamento.ativo == True,
            Rastreamento.status != RastreamentoStatus.ENTREGUE,
        ).all()

        updated, errors = 0, []
        for r in ativos:
            try:
                events, meta, inferred = parse_tracking(r.codigo_rastreio)
                r.historico_eventos = events
                r.rastreio_info = meta
                r.status = inferred
                r.ultima_atualizacao = datetime.utcnow()
                updated += 1
            except Exception as e:
                errors.append(f"{r.codigo_rastreio}: {str(e)}")

        db.commit()
        # Sync pedido statuses for all updated rastreamentos
        try:
            from .services.rastreamento_sync import RastreamentoSyncService
            for r in ativos:
                if r.pedido_id:
                    RastreamentoSyncService.sincronizar_rastreamento_com_pedido(db, r)
            db.commit()
        except Exception as e:
            logger.warning(f"[SCHEDULER] Erro ao sincronizar pedidos: {e}")
        logger.info(f"[SCHEDULER] Atualização diária: {updated} atualizados, {len(errors)} erros")
        if errors:
            logger.warning(f"[SCHEDULER] Erros: {errors}")
    except Exception as e:
        logger.error(f"[SCHEDULER] Falha na atualização diária: {e}\n{traceback.format_exc()}")
    finally:
        db.close()


scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("=" * 60)
    logger.info("[STARTUP] Starting ERP Eleven API")
    logger.info(f"[STARTUP] Python {sys.version}")
    logger.info(f"[STARTUP] LOG_LEVEL={os.getenv('LOG_LEVEL', 'INFO')}")
    db_url = os.getenv("DATABASE_URL", "")
    if db_url:
        # Log DB host only, never credentials
        try:
            from urllib.parse import urlparse
            p = urlparse(db_url)
            logger.info(f"[STARTUP] DB host={p.hostname}:{p.port} db={p.path.lstrip('/')}")
        except Exception:
            logger.info("[STARTUP] DATABASE_URL is set")
    else:
        logger.warning("[STARTUP] DATABASE_URL not set — using default")
    logger.info("=" * 60)

    # Run Alembic migrations (applies any pending migrations automatically)
    try:
        from alembic.config import Config as AlembicConfig
        from alembic import command as alembic_command
        # os is already imported at module level
        backend_dir = os.path.dirname(os.path.dirname(__file__))
        alembic_cfg = AlembicConfig(os.path.join(backend_dir, "alembic.ini"))
        alembic_cfg.set_main_option("script_location", os.path.join(backend_dir, "alembic"))
        alembic_command.upgrade(alembic_cfg, "head")
        logger.info("[DB] Alembic migrations applied successfully")
    except Exception as e:
        logger.error(f"[DB_ERROR] Alembic migration failed: {e}")
        # Fall back to create_all for tables that don't exist yet
        try:
            Base.metadata.create_all(bind=engine)
        except Exception:
            pass

    # Start daily tracking update scheduler (19:00 BRT)
    scheduler.add_job(
        _job_atualizar_rastreamentos,
        CronTrigger(hour=19, minute=0, timezone="America/Sao_Paulo"),
        id="atualizar_rastreamentos_diario",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("[SCHEDULER] Job de atualização diária de rastreamentos agendado (19:00 BRT)")

    yield

    scheduler.shutdown(wait=False)
    logger.info("[SHUTDOWN] Shutting down ERP Eleven API")

app = FastAPI(
    title="ERP Eleven API", 
    version="1.0.0",
    description="API para gerenciamento de loja de roupas com sistema ERP completo",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS - Must be first middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://erp-eleven-frontend.onrender.com",
        "https://erp-eleven-backend.onrender.com", 
        "https://erp-eleven.onrender.com",
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "Access-Control-Allow-Origin"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(vendas.router, prefix="/api/vendas", tags=["vendas"])
app.include_router(vendedores.router, prefix="/api/vendedores", tags=["vendedores"])
app.include_router(cambistas.router, prefix="/api/cambistas", tags=["cambistas"])
app.include_router(pedidos.router, prefix="/api/pedidos", tags=["pedidos"])
app.include_router(tags.router, prefix="/api/tags", tags=["tags"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(exchange_rates.router, prefix="/api/exchange-rates", tags=["exchange-rates"])
app.include_router(money_transfers.router, prefix="/api/money-transfers", tags=["money-transfers"])
app.include_router(rastreamento.router, prefix="/api/rastreamento", tags=["rastreamento"])
app.include_router(excel_import.router, prefix="/api/excel-import", tags=["excel-import"])
app.include_router(inventory.router, prefix="/api/inventory", tags=["inventory"])
app.include_router(clientes.router, prefix="/api/clientes", tags=["clientes"])

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # HSTS header for HTTPS
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing, status and query params."""
    start_time = time.time()
    qs = f"?{request.url.query}" if request.url.query else ""
    route = f"{request.method} {request.url.path}{qs}"

    # Skip noisy health-check logging at INFO
    is_health = request.url.path == "/health"

    if not is_health:
        logger.info(f"[REQ] {route}")

    try:
        response = await call_next(request)
    except Exception as exc:
        elapsed = time.time() - start_time
        logger.critical(
            f"[CRASH] {route} — unhandled exception after {elapsed:.3f}s: {exc}\n"
            f"{traceback.format_exc()}"
        )
        return JSONResponse(status_code=500, content={"detail": "Internal server error"})

    elapsed = time.time() - start_time
    status = response.status_code

    if status >= 500:
        logger.error(f"[RES] {status} {route} ({elapsed:.3f}s)")
    elif status >= 400:
        logger.warning(f"[RES] {status} {route} ({elapsed:.3f}s)")
    elif not is_health:
        logger.info(f"[RES] {status} {route} ({elapsed:.3f}s)")

    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Global HTTP exception handler"""
    qs = f"?{request.url.query}" if request.url.query else ""
    if exc.status_code >= 500:
        logger.error(
            f"[HTTP_ERROR] {exc.status_code}: {exc.detail} — "
            f"{request.method} {request.url.path}{qs}\n{traceback.format_exc()}"
        )
    else:
        logger.warning(
            f"[HTTP_WARN] {exc.status_code}: {exc.detail} — "
            f"{request.method} {request.url.path}{qs}"
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global exception handler — logs full traceback so crashes are diagnosable."""
    qs = f"?{request.url.query}" if request.url.query else ""
    logger.critical(
        f"[UNHANDLED] {type(exc).__name__}: {exc} — "
        f"{request.method} {request.url.path}{qs}\n{traceback.format_exc()}"
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500}
    )

@app.get("/", tags=["root"])
async def root():
    """API root endpoint"""
    logger.info("[ROOT] Root endpoint accessed")
    return {
        "message": "ERP Eleven API", 
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs"
    }

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint — reports API and database status."""
    from .database import SessionLocal
    from sqlalchemy import text as sql_text

    db_status = "offline"
    try:
        db = SessionLocal()
        db.execute(sql_text("SELECT 1"))
        db.close()
        db_status = "online"
    except Exception as e:
        logger.warning(f"[HEALTH] Database check failed: {e}")

    return {
        "api": "online",
        "database": db_status,
        "timestamp": time.time(),
    }


