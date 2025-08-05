from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import time
import logging
from .api.endpoints import vendas, vendedores, cambistas, auth, pedidos, dashboard, exchange_rates
from .logging_config import setup_logging, get_logger
from .database import engine, Base

# Setup logging
setup_logging(level="INFO")
logger = get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    logger.info("🚀 Starting ERP Eleven API")
    
    # Create database tables
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created/verified")
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
    
    yield
    
    logger.info("🛑 Shutting down ERP Eleven API")

app = FastAPI(
    title="ERP Eleven API", 
    version="1.0.0",
    description="API para gerenciamento de loja de roupas com sistema ERP completo",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(vendas.router, prefix="/api/vendas", tags=["vendas"])
app.include_router(vendedores.router, prefix="/api/vendedores", tags=["vendedores"])
app.include_router(cambistas.router, prefix="/api/cambistas", tags=["cambistas"])
app.include_router(pedidos.router, prefix="/api/pedidos", tags=["pedidos"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(exchange_rates.router, prefix="/api/exchange-rates", tags=["exchange-rates"])

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests"""
    start_time = time.time()
    
    # Log request
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"📨 {request.method} {request.url.path} - {client_host}")
    
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Log response
    logger.info(f"📤 {response.status_code} - {process_time:.3f}s")
    
    return response

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Global HTTP exception handler"""
    logger.error(f"❌ HTTP {exc.status_code}: {exc.detail} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "status_code": exc.status_code}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"💥 Unhandled exception: {str(exc)} - {request.method} {request.url.path}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "status_code": 500}
    )

@app.get("/", tags=["root"])
async def root():
    """API root endpoint"""
    logger.info("🏠 Root endpoint accessed")
    return {
        "message": "ERP Eleven API", 
        "version": "1.0.0",
        "status": "healthy",
        "docs": "/docs"
    }

@app.get("/health", tags=["health"])
async def health_check():
    """Health check endpoint"""
    logger.info("💊 Health check accessed")
    return {
        "status": "healthy", 
        "timestamp": time.time(),
        "version": "1.0.0"
    }