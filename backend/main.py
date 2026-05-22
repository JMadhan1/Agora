"""Oracle Sentinel API — FastAPI backend serving dashboard + agent data"""
import asyncio
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import structlog
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from storage.database import init_db
from routers import markets, attestations, agents, jobs, calibration, watchdog, eurc, nanopayments, mcp, insurance
from websocket import router as ws_router

log = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("oracle_sentinel_api_started", port=8000)
    yield
    log.info("oracle_sentinel_api_stopped")


app = FastAPI(
    title="Oracle Sentinel API",
    description="Autonomous prediction market truth verification — Arc Testnet",
    version="1.0.0",
    lifespan=lifespan,
)

_extra = os.getenv("CORS_ORIGINS", "")
_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
] + [o.strip() for o in _extra.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"https://(.*\.vercel\.app|.*\.netlify\.app|.*\.onrender\.com)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(markets.router, prefix="/api/markets", tags=["markets"])
app.include_router(attestations.router, prefix="/api/attestations", tags=["attestations"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(jobs.router, prefix="/api/jobs", tags=["jobs"])
app.include_router(calibration.router, prefix="/api/calibration", tags=["calibration"])
app.include_router(watchdog.router, prefix="/api/watchdog", tags=["watchdog"])
app.include_router(eurc.router, prefix="/api/eurc", tags=["eurc"])
app.include_router(nanopayments.router, prefix="/api/nanopayments", tags=["nanopayments"])
app.include_router(mcp.router, prefix="/mcp/v1", tags=["mcp"])
app.include_router(insurance.router, prefix="/api/insurance", tags=["insurance"])
app.include_router(ws_router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "oracle-sentinel-api", "version": "1.0.0"}


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port, reload=False)
