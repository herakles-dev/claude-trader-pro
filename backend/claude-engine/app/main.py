"""
Claude Decision Engine - FastAPI Application
Production-ready service for AI-powered crypto trading predictions

Port: 8108
Database: PostgreSQL (trading_predictions schema)
AI: Anthropic Claude 3.5 Haiku
Data Source: Unified Crypto Data API

Author: AI Integration Specialist
Date: 2025-11-11
"""

import logging
import sys
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError

# Import application components
# Add external data sources to Python path (works in both dev and container)
import os
if os.path.exists('/home/user/OctoBot'):
    sys.path.insert(0, '/home/user/OctoBot')
if os.path.exists('/app/external_data_sources'):
    sys.path.insert(0, '/app/external_data_sources')

from app.routers import predictions, automated, signals, trade_outcomes, sentiment, backtest
from app.models.prediction import Base, DatabaseConfig
from app.services import scheduler_service

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics
REQUEST_COUNT = Counter(
    'claude_engine_requests_total',
    'Total requests to Claude Decision Engine',
    ['method', 'endpoint', 'status']
)
REQUEST_LATENCY = Histogram(
    'claude_engine_request_duration_seconds',
    'Request latency in seconds',
    ['method', 'endpoint']
)
PREDICTION_COUNT = Counter(
    'claude_predictions_total',
    'Total predictions generated',
    ['symbol', 'prediction_type']
)
PREDICTION_COST = Counter(
    'claude_api_cost_usd_total',
    'Total Claude API cost in USD'
)
ACTIVE_CONNECTIONS = Gauge(
    'claude_engine_active_connections',
    'Number of active connections'
)
DATABASE_HEALTH = Gauge(
    'claude_engine_database_health',
    'Database health status (1=healthy, 0=unhealthy)'
)

# Global database session
db_session = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup: Initialize database connection
    global db_session
    
    logger.info("Starting Claude Decision Engine...")
    
    try:
        # Create database engine
        connection_string = DatabaseConfig.get_connection_string()
        engine = create_engine(
            connection_string,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True  # Verify connections before use
        )
        
        # Test connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        
        # Create session maker
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db_session = SessionLocal()
        
        DATABASE_HEALTH.set(1)
        logger.info(f"Database connected: {DatabaseConfig.DEFAULT_DATABASE}")
        
        # Store in app state
        app.state.db_engine = engine
        app.state.db_session = SessionLocal
        
    except OperationalError as e:
        logger.error(f"Database connection failed: {e}")
        logger.warning("Starting without database - predictions will not be persisted")
        DATABASE_HEALTH.set(0)
        # Continue without database - app will work with in-memory only
        app.state.db_engine = None
        app.state.db_session = None
    
    # Initialize trade tracker with database access
    if app.state.db_session:
        try:
            from app.services.trade_tracker_service import initialize_tracker
            initialize_tracker(app.state.db_session)
            logger.info("Trade tracker initialized with database access")
        except Exception as e:
            logger.error(f"Failed to initialize trade tracker: {e}")

    # Start automated prediction scheduler
    try:
        scheduler_service.start_scheduler()
        logger.info("Automated prediction scheduler started")
    except Exception as e:
        logger.error(f"Failed to start scheduler: {e}")
        logger.warning("Continuing without automated predictions - use manual trigger endpoint")
    
    logger.info("Claude Decision Engine started successfully on port 8108")
    
    yield
    
    # Shutdown: Stop scheduler and close database connections
    try:
        scheduler_service.shutdown_scheduler(wait=True)
        logger.info("Scheduler stopped gracefully")
    except Exception as e:
        logger.error(f"Error stopping scheduler: {e}")
    
    if db_session:
        db_session.close()
    if hasattr(app.state, 'db_engine'):
        app.state.db_engine.dispose()
    
    logger.info("Claude Decision Engine shutdown complete")


# FastAPI application
app = FastAPI(
    title="Claude Decision Engine",
    description="AI-powered crypto trading predictions using Claude 3.5 Haiku",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration
def get_cors_origins():
    """Get allowed CORS origins from environment"""
    origins = os.getenv('CORS_ALLOWED_ORIGINS', '')
    environment = os.getenv('ENVIRONMENT', 'development')

    if not origins:
        if environment == 'production':
            logger.warning("CORS_ALLOWED_ORIGINS not set in production - denying all cross-origin requests")
            return []
        # Development mode: allow all
        return ["*"]

    return [o.strip() for o in origins.split(',') if o.strip()]

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_cors_origins(),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)


# Request/response middleware for metrics
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """
    Middleware to track request metrics
    """
    ACTIVE_CONNECTIONS.inc()
    
    method = request.method
    path = request.url.path
    
    # Start timer
    import time
    start_time = time.time()
    
    try:
        response = await call_next(request)
        status = response.status_code
        
        # Record metrics
        REQUEST_COUNT.labels(method=method, endpoint=path, status=status).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=path).observe(time.time() - start_time)
        
        return response
        
    except Exception as e:
        REQUEST_COUNT.labels(method=method, endpoint=path, status=500).inc()
        logger.error(f"Request failed: {e}")
        raise
        
    finally:
        ACTIVE_CONNECTIONS.dec()


# Import auth middleware
from app.middleware.auth import verify_api_key

# Include routers with authentication
app.include_router(
    predictions.router,
    prefix="/api/v1",
    tags=["predictions"],
    dependencies=[Depends(verify_api_key)]
)
app.include_router(
    automated.router,
    prefix="/api/v1/automated",
    tags=["automated"],
    dependencies=[Depends(verify_api_key)]
)
app.include_router(
    signals.router,
    prefix="/api/v1/signals",
    tags=["signals"],
    dependencies=[Depends(verify_api_key)]
)
app.include_router(
    trade_outcomes.router,
    prefix="/api/v1/trades",
    tags=["trades"],
    dependencies=[Depends(verify_api_key)]
)
app.include_router(
    sentiment.router,
    prefix="/api/v1/sentiment",
    tags=["sentiment"],
    dependencies=[Depends(verify_api_key)]
)
app.include_router(
    backtest.router,
    prefix="/api/v1/backtest",
    tags=["backtest"],
    dependencies=[Depends(verify_api_key)]
)


# Root endpoint
@app.get("/", tags=["root"])
async def root():
    """
    Root endpoint - service info
    """
    return {
        "service": "Claude Decision Engine",
        "version": "1.0.0",
        "status": "operational",
        "port": 8108,
        "model": "claude-sonnet-4-20250514",
        "endpoints": {
            "predict": "/api/v1/predict",
            "predictions": "/api/v1/predictions",
            "health": "/api/v1/health",
            "costs": "/api/v1/costs",
            "signals": "/api/v1/signals/latest",
            "signals_outcome": "/api/v1/signals/outcome",
            "signals_health": "/api/v1/signals/health",
            "trades_statistics": "/api/v1/trades/statistics",
            "trades_recent": "/api/v1/trades/recent",
            "metrics": "/metrics",
            "docs": "/docs"
        }
    }


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check():
    """
    Service health check
    """
    try:
        # Check database connection
        if db_session:
            db_session.execute(text("SELECT 1"))
            db_status = "healthy"
            DATABASE_HEALTH.set(1)
        else:
            db_status = "unhealthy"
            DATABASE_HEALTH.set(0)
        
        return {
            "status": "healthy" if db_status == "healthy" else "degraded",
            "timestamp": datetime.utcnow().isoformat(),
            "database": db_status,
            "service": "operational"
        }
        
    except Exception as e:
        DATABASE_HEALTH.set(0)
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.utcnow().isoformat(),
                "error": str(e)
            }
        )


# Prometheus metrics endpoint
@app.get("/metrics", tags=["monitoring"])
async def metrics():
    """
    Prometheus metrics endpoint
    """
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(generate_latest())


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8108,
        reload=False,  # Production: disable reload
        log_level="info"
    )
