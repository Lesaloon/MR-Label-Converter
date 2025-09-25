"""Core conversion utilities for Mondial Relay / InPost PDF labels."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Tuple

import fitz  # type: ignore[attr-defined]

PRESETS: dict[str, Tuple[float, float]] = {
    "a4": (595.276, 841.89),
    "letter": (612.0, 792.0),
}


class PageSizeError(ValueError):
    """Raised when a provided page size cannot be parsed."""


def parse_page_size(value: str | Tuple[float, float]) -> Tuple[float, float]:
    """Parse a named or explicit page size definition into (width, height)."""

    if isinstance(value, tuple):
        if len(value) != 2:
            raise PageSizeError("Tuple page size must contain (width, height).")
        return float(value[0]), float(value[1])

    parsed = value.lower().strip()
    if parsed in PRESETS:
        return PRESETS[parsed]

    match = re.match(r"^\s*(\d+(?:\.\d+)?)x(\d+(?:\.\d+)?)\s*$", parsed)
    if not match:
        raise PageSizeError(
            "Invalid page size format. Use 'a4', 'letter', or 'WIDTHxHEIGHT' in points (e.g. 595x842)."
        )
    return float(match.group(1)), float(match.group(2))


@dataclass(slots=True)
class ConversionConfig:
    """Configuration options controlling how labels are converted."""

    left_ratio: float | None = None
    auto_left_min: float = 0.45
    auto_left_margin: float = 8.0
    auto_left_gap: float = 25.0
    rotate: int = 90
    page: str | Tuple[float, float] = "a4"
    margin: float = 12.0
    fit: str = "contain"
    scale: float = 2.0
    fill_width: bool = True
    halign: str = "auto"
    halign_offset: float = -6.0
    halign_bleed: float = 30.0
    valign: str = "top"
    debug_boxes: bool = False


def place_pdf(
    dst_page: fitz.Page,
    src_doc: fitz.Document,
    pno: int,
    clip_rect: fitz.Rect,
    target_rect: fitz.Rect,
    *,
    rotation: int,
    fit_mode: str,
    extra_scale: float,
    fill_width: bool,
    halign: str,
    halign_offset: float,
    halign_bleed: float,
    valign: str,
    debug: bool,
) -> None:
    """Place a cropped source page into the destination rectangle."""

    cw, ch = clip_rect.width, clip_rect.height
    tw, th = target_rect.width, target_rect.height

    rot = int(rotation) % 360
    if rot not in (0, 90, 180, 270):
        rot = 90

    if rot in (90, 270):
        sw, sh = ch, cw
    else:
        sw, sh = cw, ch

    width_scale = tw / sw
    height_scale = th / sh

    if fit_mode == "cover":
        scale = max(width_scale, height_scale) * float(extra_scale)
    else:
        scale = min(width_scale, height_scale) * float(extra_scale)
        if fill_width and width_scale <= height_scale:
            scale = width_scale * float(extra_scale)

    nw, nh = sw * scale, sh * scale

    if halign == "left":
        x0 = target_rect.x0
    elif halign == "right":
        x0 = target_rect.x1 - nw
    elif halign == "center":
        x0 = target_rect.x0 + (tw - nw) / 2
    else:
        if nw <= tw:
            x0 = target_rect.x0 + (tw - nw) / 2
        else:
            x0 = target_rect.x0

    x0 += halign_offset

    min_x = target_rect.x0 - float(halign_bleed)
    max_x = target_rect.x1 - nw + float(halign_bleed)
    if max_x < min_x:
        max_x = min_x
    x0 = max(min_x, min(max_x, x0))

    if valign == "top":
        y0 = target_rect.y0
    elif valign == "bottom":
        y0 = target_rect.y1 - nh
    else:
        y0 = target_rect.y0 + (th - nh) / 2

    dest_rect = fitz.Rect(x0, y0, x0 + nw, y0 + nh)

    if debug:
        shape = dst_page.new_shape()
        shape.draw_rect(target_rect)
        shape.draw_rect(dest_rect)
        shape.finish(width=0.6)
        shape.commit()

    dst_page.show_pdf_page(dest_rect, src_doc, pno=pno, clip=clip_rect, rotate=rot)


def auto_detect_left_ratio(
    page: fitz.Page,
    *,
    dpi: float = 150.0,
    min_ratio: float = 0.45,
    threshold: int = 245,
    blank_ratio: float = 0.0,
    blank_run_px: float = 25.0,
    extra_margin_px: float = 8.0,
) -> float:
    """Estimate how much of the page width to keep based on blank space detection."""

    scale = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
    width, height = pix.width, pix.height
    samples = pix.samples

    blanks = 0
    seen_content = False
    blank_start = width
    run_threshold = max(1, int(blank_run_px))
    blank_threshold = max(0, int(height * blank_ratio))

    for x in range(width):
        dark_pixels = 0
        offset = x
        for _ in range(height):
            if samples[offset] < threshold:
                dark_pixels += 1
            offset += width

        if dark_pixels <= blank_threshold:
            if seen_content:
                if blanks == 0:
                    blank_start = x
                blanks += 1
                if blanks >= run_threshold:
                    cut_idx = min(width, blank_start + int(extra_margin_px))
                    ratio = cut_idx / width
                    return max(min_ratio, min(1.0, ratio))
        else:
            seen_content = True
            blanks = 0

    return 1.0


def _compute_clips(
    pages: Iterable[int],
    src: fitz.Document,
    cfg: ConversionConfig,
) -> list[fitz.Rect]:
    clips: list[fitz.Rect] = []
    for i in pages:
        src_page = src[i]
        rect = src_page.rect
        if cfg.left_ratio is None:
            ratio = auto_detect_left_ratio(
                src_page,
                min_ratio=cfg.auto_left_min,
                blank_run_px=cfg.auto_left_gap,
                extra_margin_px=cfg.auto_left_margin,
            )
        else:
            ratio = cfg.left_ratio
            if not (0.0 < ratio <= 1.0):
                raise ValueError("left_ratio must be within (0, 1].")
        keep_w = rect.width * ratio
        clips.append(fitz.Rect(rect.x0, rect.y0, rect.x0 + keep_w, rect.y1))
    return clips


def convert_pdf(
    input_path: str | Path,
    output_path: str | Path,
    config: ConversionConfig | None = None,
) -> None:
    """Convert a Mondial Relay label PDF into the desired format."""

    cfg = config or ConversionConfig()
    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Input PDF not found: {input_path}")

    out_w, out_h = parse_page_size(cfg.page)
    if out_h < out_w:
        out_w, out_h = out_h, out_w

    target_rect = fitz.Rect(cfg.margin, cfg.margin, out_w - cfg.margin, out_h - cfg.margin)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with fitz.open(input_path) as src, fitz.open() as dst:
        pages = list(range(len(src)))
        clips = _compute_clips(pages, src, cfg)

        for idx, clip in zip(pages, clips):
            page = dst.new_page(width=out_w, height=out_h)  # type: ignore[attr-defined]
            place_pdf(
                page,
                src,
                idx,
                clip,
                target_rect,
                rotation=cfg.rotate,
                fit_mode=cfg.fit,
                extra_scale=cfg.scale,
                fill_width=cfg.fill_width,
                halign=cfg.halign,
                halign_offset=cfg.halign_offset,
                halign_bleed=cfg.halign_bleed,
                valign=cfg.valign,
                debug=cfg.debug_boxes,
            )

        dst.save(str(output_path))
