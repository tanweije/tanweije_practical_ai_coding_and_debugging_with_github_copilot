## Features

- REST API for ticket creation, listing, updating, and deletion
- Embedded DuckDB database stored at `data/tickets.duckdb` by default
- NiceGUI web interface for creating, filtering, and updating tickets
- Seeded sample tickets on first run
- Many deliberate bugs for participants to diagnose and repair

## Run Locally

```powershell
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

Then open http://localhost:8000.
