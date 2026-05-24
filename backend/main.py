"""
NBFC Audit Intelligence Platform — FastAPI Backend
Complete audit management system for NBFC loans portfolio
"""

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from core.config import settings
from core.database import init_db, get_db
from api import auth, engagement, cap, exceptions, suam, analytics, financial, credit_policy, ws

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """App startup and shutdown logic"""
    logger.info("Starting NBFC Audit Platform...")
    await init_db()
    logger.info("Database initialized")
    yield
    logger.info("Shutting down NBFC Audit Platform...")


app = FastAPI(
    title="NBFC Audit Intelligence Platform",
    description="Complete audit management system for NBFC loans portfolio",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trusted Host Middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1", "*.example.com"]
)


# Health Check
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "NBFC Audit Intelligence Platform",
        "version": "1.0.0"
    }


# Include API routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(engagement.router, prefix="/api/engagement", tags=["engagement"])
app.include_router(cap.router, prefix="/api/cap", tags=["audit-program"])
app.include_router(exceptions.router, prefix="/api/exceptions", tags=["exceptions"])
app.include_router(suam.router, prefix="/api/suam", tags=["suam"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(financial.router, prefix="/api/financial", tags=["financial"])
app.include_router(credit_policy.router, prefix="/api/credit-policy", tags=["credit-policy"])

# WebSocket endpoint
@app.websocket("/ws/{engagement_id}")
async def websocket_endpoint(websocket: WebSocket, engagement_id: str):
    await ws.connection_manager.connect(websocket, engagement_id)
    try:
        while True:
            data = await websocket.receive_text()
            await ws.connection_manager.broadcast(engagement_id, data)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        ws.connection_manager.disconnect(websocket, engagement_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.BACKEND_RELOAD,
        log_level=settings.LOG_LEVEL.lower()
    )
