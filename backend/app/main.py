from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from contextlib import asynccontextmanager
import time
import logging
import sys
import threading
import asyncio
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from .api.endpoints import vendas, vendedores, cambistas, auth, pedidos, dashboard, exchange_rates, money_transfers, rastreamento, excel_import, tags, inventory, clientes, ocr, pdv
from .logging_config import setup_logging, get_logger
from .database import engine, Base, SessionLocal
from .config import settings
from .api.endpoints import assistant, printing, address_manager, freight, sales_bi, sales_bi_entries
from .services import assistant_events  # register atomic tracking outbox listener
from .api.endpoints import user_admin, product_photo
from .services import user_audit

# Main
# Setup logging
import os
log_level = os.getenv("LOG_LEVEL", "INFO")  # Default to INFO for better tracking
setup_logging(level=log_level)
logger = get_logger(__name__)

def _job_atualizar_rastreamentos():
    from .services.scheduled_tracking import run_daily
    try:
        result = run_daily()
        if result is not None:
            logger.info('[SCHEDULER] tracking updated=%d errors=%d skipped=%d',
                        result['updated'],len(result['errors']),len(result['skipped']))
    except Exception as exc:
        logger.error('[SCHEDULER] tracking failed type=%s',type(exc).__name__)


scheduler = BackgroundScheduler(timezone="America/Sao_Paulo")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    settings.validate_runtime()
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
        setup_logging(level=log_level)
        logger.info("[DB] Alembic migrations applied successfully")
    except Exception as e:
        logger.error("[DB_ERROR] Migration failed type=%s", type(e).__name__)
        raise RuntimeError('A migração do banco falhou; a API não iniciará com esquema incompleto.') from e

    # Start daily tracking update scheduler (19:00 BRT)
    scheduler.add_job(
        _job_atualizar_rastreamentos,
        CronTrigger(hour=19, minute=0, timezone="America/Sao_Paulo"),
        id="atualizar_rastreamentos_diario",
        replace_existing=True,
        max_instances=1, coalesce=True, misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("[SCHEDULER] Job de atualização diária de rastreamentos agendado (19:00 BRT)")

    from .services.assistant_knowledge import system_catalog, KnowledgeArgs
    with SessionLocal() as catalog_db:
        system_catalog(catalog_db, KnowledgeArgs())
        catalog_db.commit()

    worker_stop = threading.Event()
    from .services.freight_labels import main as run_label_worker
    app.state.label_worker = threading.Thread(target=run_label_worker, args=(worker_stop,), name="freight-label-worker", daemon=True)
    app.state.label_worker.start()
    from .services.sales_bi_sync import main as run_sales_bi_worker
    app.state.sales_bi_worker = threading.Thread(target=run_sales_bi_worker, args=(worker_stop,), name="sales-bi-worker", daemon=True)
    app.state.sales_bi_worker.start()
    app.state.assistant_worker = None
    if settings.ASSISTANT_ENABLED and settings.ASSISTANT_EMBEDDED_WORKER:
        # Dedicated thread: provider requests never block the API event loop.
        # PostgreSQL locks also serialize workers during overlapping deploys.
        from .assistant_worker import main as run_assistant_worker
        from sqlalchemy import inspect
        required = {"assistant_identities", "assistant_messages", "assistant_notes", "assistant_deliveries", "assistant_actions"}
        if not required.issubset(set(inspect(engine).get_table_names())):
            raise RuntimeError("Assistant tables missing; apply the migration before activation")
        app.state.assistant_worker = threading.Thread(
            target=run_assistant_worker, args=(worker_stop,), name="assistant-worker", daemon=True)
        app.state.assistant_worker.start()
        logger.info("[ASSISTANT] Embedded worker started")

    try:
        yield
    finally:
        worker_stop.set()
        await asyncio.to_thread(app.state.label_worker.join, 5)
        await asyncio.to_thread(app.state.sales_bi_worker.join, 5)
        if app.state.assistant_worker:
            await asyncio.to_thread(app.state.assistant_worker.join, 5)
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
        "https://elevenparispy.com",
        "https://www.elevenparispy.com",
        "https://erp-eleven-backend.onrender.com", 
        "https://erp-eleven.onrender.com",
        "http://localhost:3000",
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "Origin", "X-Requested-With", "Access-Control-Allow-Origin"],
)

app.include_router(user_admin.router, prefix="/api/access", tags=["access"])
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
app.include_router(ocr.router, prefix="/api/ocr", tags=["ocr"])
app.include_router(product_photo.router, prefix="/api/product-photo", tags=["Product photo"])
app.include_router(pdv.router, prefix="/api/pdv", tags=["pdv"])
app.include_router(assistant.router, prefix="/api/assistant", tags=["assistant"])
app.include_router(freight.router, prefix='/api/freight', tags=['freight'])
app.include_router(address_manager.router, prefix='/api/address-manager', tags=['address-manager'])
app.include_router(printing.router, prefix="/api/printing", tags=["printing"])
app.include_router(sales_bi.router, prefix="/api/sales-bi", tags=["sales-bi"])
app.include_router(sales_bi_entries.router, prefix='/api/sales-bi', tags=['sales-bi'])

@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses"""
    response = await call_next(request)
    
    # Security headers
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store, private"
        response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "0"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    
    # HSTS header for HTTPS
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    
    return response

@app.middleware("http")
async def log_requests(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.monotonic()
    try:
        response = await call_next(request)
    except Exception as exc:
        logger.error('[CRASH] request_id=%s type=%s',request_id,type(exc).__name__)
        response = JSONResponse(status_code=500, content={"detail": "Internal server error"})
    route = getattr(request.scope.get('route'),'path','unmatched')
    response.headers['X-Request-ID'] = request_id
    if route not in ('/health','/live'):
        logger.log(logging.ERROR if response.status_code>=500 else logging.INFO,
                   '[HTTP] request_id=%s method=%s route=%s status=%d duration_ms=%.1f',
                   request_id,request.method,route,response.status_code,(time.monotonic()-start_time)*1000)
    return response

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Pydantic's default response echoes the submitted input, including passwords.
    errors = [{key: error[key] for key in ('type', 'loc', 'msg') if key in error}
              for error in exc.errors()]
    return JSONResponse(status_code=422, content={'detail': errors})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code,headers=exc.headers,
                        content={"detail": exc.detail, "status_code": exc.status_code})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error('[UNHANDLED] request_id=%s type=%s',getattr(request.state,'request_id','unknown'),type(exc).__name__)
    return JSONResponse(status_code=500,content={"detail":"Internal server error","status_code":500})

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

@app.get('/live', tags=['health'])
def liveness():
    return {'api':'online'}

@app.get("/health", tags=["health"])
def health_check():
    """Bounded DB readiness and actual worker progress, outside the async event loop."""
    from sqlalchemy import text
    from .services.worker_health import state
    database = 'offline'
    try:
        with SessionLocal() as db:
            if db.bind.dialect.name == 'postgresql':
                db.execute(text("SET LOCAL statement_timeout = '2000ms'"))
            db.execute(text('SELECT 1'))
            database = 'online'
    except Exception as exc:
        logger.warning('[HEALTH] database unavailable type=%s',type(exc).__name__)
    assistant = state('assistant',getattr(app.state,'assistant_worker',None)) if settings.ASSISTANT_ENABLED and settings.ASSISTANT_EMBEDDED_WORKER else 'disabled'
    labels = state('labels',getattr(app.state,'label_worker',None))
    sales_bi = state('sales_bi',getattr(app.state,'sales_bi_worker',None))
    healthy = database=='online' and assistant in ('disabled','online') and labels=='online' and sales_bi=='online'
    return JSONResponse(status_code=200 if healthy else 503,headers={'Cache-Control':'no-store'},content={
        'api':'online','database':database,'assistant_worker':assistant,'label_worker':labels,
        'sales_bi_worker':sales_bi,'timestamp':time.time()})
