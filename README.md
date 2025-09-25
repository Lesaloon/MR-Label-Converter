# Mondial Relay Label Converter

Library + FastAPI web service that reshapes Mondial Relay / InPost PDF labels into a printable format, complete with a lightweight web UI.

> ⚠️ **Disclaimer:** this codebase was mostly vibe-coded as a personal convenience tool. Treat it as untrusted: review it carefully before exposing it to the public internet or handling sensitive data. Expect rough edges and potential security holes.

## Features

- ✅ Reusable Python library (`label_converter`) with configurable conversion settings
- ✅ FastAPI backend that exposes a `/convert` endpoint and a `/health` check
- ✅ Minimal frontend (`/ui`) for drag-and-drop style conversions directly from the browser
- ♻️ Backwards-compatible CLI wrapper via `labels_fix.py` for existing scripts

## Prerequisites

- Python 3.11 or newer (PyMuPDF requires a fairly recent Python build)
- System dependencies for PyMuPDF (on Windows these install automatically via wheels)

## Installation

```bash
python -m venv .venv
source .venv/Scripts/activate  # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Running the API + Frontend

```bash
uvicorn app.main:app --reload
```

Then open <http://127.0.0.1:8000/ui/> in your browser. The root path `/` automatically redirects to the UI.

## Docker Deployment

Build and launch both the API and the frontend via Docker Compose:

```bash
docker compose up --build
```

- Frontend: <http://127.0.0.1:8080>
- Backend (direct API access): <http://127.0.0.1:8000>

The nginx frontend proxies `/convert` and `/health` to the backend container, so the static UI continues to call relative URLs.

### Inspecting Logs

If a conversion fails, check the backend container logs for the stack trace:

```bash
docker compose logs backend
```

The API now emits detailed messages when conversions error out, and the HTTP response will include the underlying exception text.

## API Reference

- `GET /health` → `{ "status": "ok" }`
- `POST /convert` → accepts a form-data upload named `file`; responds with the converted PDF. Returns `415` for non-PDF uploads.

Example `curl` usage:

```bash
curl -X POST \
  -F "file=@inputs/your-label.pdf" \
  --output outputs/your-label-converted.pdf \
  http://127.0.0.1:8000/convert
```

## Library Usage

```python
from label_converter import ConversionConfig, convert_pdf

convert_pdf(
  "inputs/your-label.pdf",
  "outputs/your-label.pdf",
    ConversionConfig(scale=2.0, fit="contain"),
)
```

Configuration mirrors the previous CLI flags and can be customised per call.

## Development Notes

- Static assets live in `frontend/` and are served from `/ui`.
- Temporary files created during API calls are confined to the OS temp directory and removed immediately after the response is returned.
- The project keeps the historical `labels_fix.py` entry point for backwards compatibility, now delegating to the new library.
- `inputs/` and `outputs/` stay in version control with `.gitkeep` placeholders. Place your PDFs there locally—the files are ignored by Git.

## Testing

A quick syntax pass can be done with:

```bash
python -m compileall label_converter app
```

You can also run `uvicorn` locally and try converting the sample PDFs under `inputs/`.
