"""FastAPI application exposing the label conversion service."""

from __future__ import annotations

import logging
import mimetypes
import shutil
from pathlib import Path
from tempfile import mkdtemp
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.responses import Response

from label_converter import ConversionConfig, convert_pdf

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"

app = FastAPI(title="Label Converter API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", summary="Health check", tags=["system"])
async def healthcheck() -> JSONResponse:
    return JSONResponse({"status": "ok"})


@app.get("/", include_in_schema=False, response_model=None)
async def root() -> Response:
    if FRONTEND_DIR.exists():
        return RedirectResponse(url="/ui/", status_code=302)
    return JSONResponse(
        {
            "message": "Label Converter API is running. The web UI is hosted separately under the frontend container on port 8080.",
            "health": "/health",
        }
    )


def _validate_upload(upload: UploadFile) -> None:
    if not upload.filename:
        raise HTTPException(status_code=400, detail="No filename provided.")

    content_type = upload.content_type or mimetypes.guess_type(upload.filename)[0]
    if content_type not in {"application/pdf", "application/x-pdf"}:
        raise HTTPException(status_code=415, detail="Only PDF files are supported.")


@app.post("/convert", summary="Convert a Mondial Relay label", tags=["conversion"])
async def convert_endpoint(file: Annotated[UploadFile, File(...)]) -> FileResponse:
    _validate_upload(file)

    tmp_dir_path = Path(mkdtemp(prefix="label-converter-"))
    input_path = tmp_dir_path / "input.pdf"
    output_path = tmp_dir_path / "output.pdf"

    try:
        with input_path.open("wb") as buffer:
            while chunk := await file.read(4096):
                buffer.write(chunk)

        await file.seek(0)

        convert_pdf(input_path, output_path, ConversionConfig())
    except FileNotFoundError as exc:
        shutil.rmtree(tmp_dir_path, ignore_errors=True)
        logger.warning("Input PDF missing during conversion: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected failures
        shutil.rmtree(tmp_dir_path, ignore_errors=True)
        logger.exception("Conversion failed for '%s'", file.filename)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc

    filename = Path(file.filename).stem + "-converted.pdf"
    background = BackgroundTask(shutil.rmtree, tmp_dir_path, ignore_errors=True)
    return FileResponse(
        path=output_path,
        media_type="application/pdf",
        filename=filename,
        background=background,
    )


if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
