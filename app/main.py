"""FastAPI application exposing the label conversion service."""

from __future__ import annotations

import logging
import mimetypes
import re
import shutil
import zipfile
from io import BytesIO
from pathlib import Path
from tempfile import mkdtemp
from typing import Annotated

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from starlette.background import BackgroundTask
from starlette.responses import Response

from label_converter import ConversionConfig, convert_pdf, convert_to_combined_pdf

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


def _safe_output_name(original: str | None, index: int) -> str:
    fallback = f"file-{index}"
    if not original:
        base = fallback
    else:
        base = Path(original).stem or fallback
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._") or fallback
    return f"{sanitized}-converted.pdf"


@app.post("/convert", summary="Convert Mondial Relay labels", tags=["conversion"], response_model=None)
async def convert_endpoint(
    files: Annotated[
        list[UploadFile],
        File(description="One or more PDF files", media_type="application/pdf"),
    ]
) -> Response:
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded.")

    tmp_dir_path = Path(mkdtemp(prefix="label-converter-"))
    converted_entries: list[tuple[Path, str]] = []
    original_inputs: list[Path] = []
    config = ConversionConfig()

    try:
        for idx, upload in enumerate(files, start=1):
            _validate_upload(upload)
            input_path = tmp_dir_path / f"input-{idx}.pdf"
            output_path = tmp_dir_path / f"output-{idx}.pdf"

            with input_path.open("wb") as buffer:
                while chunk := await upload.read(1 << 16):
                    buffer.write(chunk)

            await upload.seek(0)

            convert_pdf(input_path, output_path, config)
            arcname = _safe_output_name(upload.filename, idx)
            converted_entries.append((output_path, arcname))
            original_inputs.append(input_path)

        if original_inputs:
            combined_path = tmp_dir_path / "combined-two-per-page.pdf"
            convert_to_combined_pdf(original_inputs, combined_path, config)
            converted_entries.append((combined_path, "combined-two-per-page.pdf"))

        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
            for file_path, arcname in converted_entries:
                archive.write(file_path, arcname=arcname)
        zip_buffer.seek(0)

    except FileNotFoundError as exc:
        shutil.rmtree(tmp_dir_path, ignore_errors=True)
        logger.warning("Input PDF missing during conversion: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - defensive guard for unexpected failures
        shutil.rmtree(tmp_dir_path, ignore_errors=True)
        filenames = ", ".join(filter(None, (f.filename for f in files))) or "<unnamed>"
        logger.exception("Conversion failed for: %s", filenames)
        raise HTTPException(status_code=500, detail=f"Conversion failed: {exc}") from exc

    background = BackgroundTask(shutil.rmtree, tmp_dir_path, ignore_errors=True)
    headers = {
        "Content-Disposition": "attachment; filename=converted-labels.zip",
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers, background=background)


if FRONTEND_DIR.exists():
    app.mount("/ui", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
