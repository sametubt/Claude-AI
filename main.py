"""FastAPI server for the SET100 stock scanner.

Run:
    pip install -r requirements.txt
    python main.py

Then open http://localhost:8000
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from scanner import scan_all, scan_one

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("main")

CACHE_TTL = 15 * 60  # 15 minutes
STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="SET100 Stock Scanner")

_cache_lock = threading.Lock()
_cache: dict = {"data": None, "ts": 0.0, "scanning": False}


def _is_fresh() -> bool:
    return _cache["data"] is not None and (time.time() - _cache["ts"]) < CACHE_TTL


def _refresh(force: bool = False) -> list[dict]:
    """Run a scan if cache is stale. Returns the cached payload."""
    with _cache_lock:
        if not force and _is_fresh():
            return _cache["data"]
        if _cache["scanning"]:
            # Another thread already scanning — return whatever we have (may be None)
            return _cache["data"] or []
        _cache["scanning"] = True

    try:
        log.info("starting SET100 scan...")
        data = scan_all()
        with _cache_lock:
            _cache["data"] = data
            _cache["ts"] = time.time()
        return data
    finally:
        with _cache_lock:
            _cache["scanning"] = False


def _background_loop() -> None:
    while True:
        try:
            _refresh(force=True)
        except Exception as e:  # noqa: BLE001
            log.exception("background refresh failed: %s", e)
        time.sleep(CACHE_TTL)


@app.on_event("startup")
def _on_startup() -> None:
    threading.Thread(target=_background_loop, daemon=True).start()


@app.get("/api/scan")
def api_scan():
    data = _refresh(force=False)
    return JSONResponse({
        "count": len(data),
        "cached_at": _cache["ts"],
        "ttl_seconds": CACHE_TTL,
        "results": data,
    })


@app.get("/api/stock/{ticker}")
def api_stock(ticker: str):
    result = scan_one(ticker)
    if result is None:
        raise HTTPException(status_code=404, detail=f"{ticker} not in SET100")
    return result


@app.get("/")
def root():
    index = STATIC_DIR / "index.html"
    if not index.exists():
        return JSONResponse({"error": "frontend missing"}, status_code=500)
    return FileResponse(index)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
