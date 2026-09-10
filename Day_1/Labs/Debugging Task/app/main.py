import os
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from nicegui import app as nicegui_app, ui
import uvicorn

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.api import create_api_router
from app.database import TicketRepository
from app.ui import mount_ui


def create_app(database_path: str | None = None, seed: bool = True) -> FastAPI:
    repository = TicketRepository(database_path or os.getenv("TICKET_DB_PATH", "data/tickets.duckdb"))
    if seed:
        repository.seed_defaults()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            repository.close()

    app = FastAPI(title="Ticketing System", version="0.1.0", lifespan=lifespan)
    app.include_router(create_api_router(repository))

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    mount_ui(repository)
    ui.run_with(app, title="Ticketing System", favicon="T", storage_secret=os.getenv("NICEGUI_SECRET", "dev-secret"))
    return app


app = create_app()


if __name__ in {"__main__", "__mp_main__"}:
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("PORT", "8000")))
