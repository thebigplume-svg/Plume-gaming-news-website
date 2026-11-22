#!/usr/bin/env python3
"""
Auto-generate eye-catching 9:16 thumbnails for Shorts.

For every video in an input folder this script:
  1. samples frames across the clip with ffmpeg,
  2. scores each frame (sharpness, colour, exposure, contrast) and keeps
     the best one,
  3. punches it up (contrast, saturation, sharpening, vignette, glow),
  4. stamps a huge outlined headline, an optional sticker ("NEW!",
     "LEAKED", ...) and the Plume logo,
  5. writes a 1080x1920 JPG (well under YouTube's 2 MB limit).

Headlines come from, in order of priority:
  - a `titles.json` in the input folder: {"my-clip.mp4": {"title": "...", "badge": "NEW"}}
    (a plain string value is also accepted as the title),
  - a sidecar text file next to the video (`my-clip.txt`; first line is
    the title, an optional second line is the badge),
  - the file name itself (`elden-ring-dlc-*leaked*.mp4` -> ELDEN RING DLC LEAKED).

Wrap words in *asterisks* to paint them in the accent colour; otherwise
the longest word is highlighted automatically.

Usage:
    python3 thumbnails/make_thumbnails.py VIDEO_DIR [-o OUT_DIR] [--force]
    python3 thumbnails/make_thumbnails.py clip.mp4 --title "GTA 6 *DELAYED*" --badge "BREAKING"

Requires: ffmpeg/ffprobe on PATH, Pillow, numpy.
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

HERE = Path(__file__).resolve().parent
CONFIG_PATH = HERE / "config.json"
VIDEO_EXTS = {".mp4", ".mov", ".m4v", ".webm", ".mkv", ".avi"}

DEFAULT_CONFIG = {
    "width": 1080,
    "height": 1920,
    "samples": 24,
    "accent": "#F5A300",
    "text": "#FFFFFF",
    "stroke": "#0B1240",
    "shade": "#22318F",
    "badge_bg": "#E8202A",
    "badge_text": "#FFFFFF",
    "logo": "assets/logo.png",
    "show_logo": True,
    "text_top": 0.19,
    "text_bottom": 0.56,
    "max_lines": 3,
    "condense": 0.86,
    "saturation": 1.35,
    "contrast": 1.18,
    "jpeg_quality": 92,
    "fonts": [
        "fonts/*.ttf",
        "fonts/*.otf",
        "/usr/share/fonts/**/Anton*.ttf",
        "/usr/share/fonts/**/BebasNeue*.ttf",
        "/usr/share/fonts/**/Impact*.ttf",
        "/usr/share/fonts/**/Montserrat-Black*.ttf",
        "/usr/share/fonts/**/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/**/LiberationSans-Bold.ttf",
        "/Library/Fonts/Impact.ttf",
        "/System/Library/Fonts/Supplemental/Impact.ttf",
        "C:/Windows/Fonts/impact.ttf",
    ],
}


# ----------------------------------------------------------------- config

def load_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if CONFIG_PATH.exists():
        user = json.loads(CONFIG_PATH.read_text())
        cfg.update({k: v for k, v in user.items() if not k.startswith("_")})
    return cfg


def find_font(cfg: dict, override: str | None) -> str:
    if override:
        return override
    for pattern in cfg["fonts"]:
        p = Path(pattern)
        base = p if p.is_absolute() else HERE / p
        anchor = Path(base.anchor) if base.is_absolute() else HERE
        rel = str(base.relative_to(anchor))
        hits = sorted(anchor.glob(rel))
        if hits:
            return str(hits[0])
    raise SystemExit("No usable bold font found. Drop a .ttf (e.g. Anton) into thumbnails/fonts/.")


# ------------------------------------------------------------------ video

def need(tool: str) -> None:
    if not shutil.which(tool):
        raise SystemExit(f"{tool} not found on PATH — install ffmpeg first.")


def duration(video: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(video)],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    return float(out or 0)


def grab_frame(video: Path, t: float, dest: Path) -> Path | None:
    r = subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.3f}", "-i", str(video),
         "-frames:v", "1", "-q:v", "2", str(dest)],
        capture_output=True,
    )
    return dest if r.returncode == 0 and dest.exists() else None


def score_frame(img: Image.Image) -> float:
    """Higher = better thumbnail candidate."""
    small = img.convert("RGB").resize((180, 320))
    a = np.asarray(small, dtype=np.float32) / 255.0
    gray = a @ np.array([0.299, 0.587, 0.114], dtype=np.float32)

    # sharpness: variance of a Laplacian
    lap = (-4 * gray[1:-1, 1:-1] + gray[:-2, 1:-1] + gray[2:, 1:-1]
           + gray[1:-1, :-2] + gray[1:-1, 2:])
    sharp = float(lap.var()) * 1000

    # colourfulness (Hasler & Süsstrunk)
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    rg, yb = r - g, 0.5 * (r + g) - b
    colour = math.hypot(rg.std(), yb.std()) + 0.3 * math.hypot(rg.mean(), yb.mean())

    mean = float(gray.mean())
    exposure = math.exp(-((mean - 0.48) ** 2) / 0.04)   # penalise too dark/bright
    contrast = float(gray.std())

    if mean < 0.06 or mean > 0.95 or contrast < 0.03:     # black/white/flat frames
        return 0.0
    return (0.6 + math.log1p(sharp)) * (0.4 + colour * 3) * exposure * (0.5 + contrast * 2)


def best_frame(video: Path, samples: int, keep_dir: Path | None = None) -> Image.Image:
    dur = duration(video)
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        stamps = [dur * (0.04 + 0.88 * i / max(samples - 1, 1)) for i in range(samples)] if dur > 0 else [0.0]
        scored = []
        for i, t in enumerate(stamps):
            f = grab_frame(video, t, tmpd / f"f{i:03d}.jpg")
            if f:
                img = Image.open(f).convert("RGB")
                img.load()
                scored.append((score_frame(img), t, img))
        if not scored:
            raise RuntimeError(f"could not read any frames from {video.name}")
        scored.sort(key=lambda s: s[0], reverse=True)
        if keep_dir:
            keep_dir.mkdir(parents=True, exist_ok=True)
            for rank, (s, t, img) in enumerate(scored[:5], 1):
                img.save(keep_dir / f"{video.stem}_cand{rank}_{t:.1f}s.jpg", quality=85)
        return scored[0][2]


# ---------------------------------------------------------------- styling

def hex_rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def fit_cover(img: Image.Image, w: int, h: int) -> Image.Image:
    """Fill a 9:16 canvas. Non-vertical sources get a blurred backdrop."""
    ratio = img.width / img.height
    if abs(ratio - w / h) < 0.06:
        return ImageOps.fit(img, (w, h), Image.LANCZOS)
    bg = ImageOps.fit(img, (w, h), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
    bg = ImageEnhance.Brightness(bg).enhance(0.6)
    fg = ImageOps.contain(img, (w, int(h * 0.62)), Image.LANCZOS)
    fg = ImageOps.fit(img, (w, min(fg.height, h)), Image.LANCZOS) if ratio > w / h else fg
    bg.paste(fg, ((w - fg.width) // 2, int(h * 0.52 - fg.height / 2)))
    return bg


def punch_up(img: Image.Image, cfg: dict) -> Image.Image:
    img = ImageOps.autocontrast(img, cutoff=1)
    img = ImageEnhance.Contrast(img).enhance(cfg["contrast"])
    img = ImageEnhance.Color(img).enhance(cfg["saturation"])
    img = img.filter(ImageFilter.UnsharpMask(radius=3, percent=110, threshold=2))
    # soft "bloom": screen a blurred copy over the top
    glow = img.filter(ImageFilter.GaussianBlur(18))
    img = Image.blend(img, ImageChops.screen(img, glow), 0.22)
    return img


def vignette_and_shade(img: Image.Image, cfg: dict) -> Image.Image:
    w, h = img.size
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    d = np.sqrt(((xx - w / 2) / (w * 0.75)) ** 2 + ((yy - h / 2) / (h * 0.75)) ** 2)
    vig = np.clip(1.0 - (d ** 2.2) * 0.85, 0.25, 1.0)

    # darken behind the headline band and at the very bottom (Shorts UI)
    ty = (cfg["text_top"] + cfg["text_bottom"]) / 2
    band = np.exp(-(((yy / h) - ty) ** 2) / 0.018) * 0.45
    bottom = np.clip((yy / h - 0.72) / 0.28, 0, 1) ** 1.5 * 0.55
    dark = np.clip(vig * (1 - band) * (1 - bottom), 0, 1)

    arr = np.asarray(img, dtype=np.float32)
    shade = np.array(hex_rgb(cfg["shade"]), dtype=np.float32) * 0.35
    out = arr * dark[..., None] + shade * (1 - dark[..., None])
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8))


# ------------------------------------------------------------------ text

def parse_title(raw: str) -> tuple[list[str], set[int]]:
    """Return upper-cased words and the indices to highlight."""
    words, hi = [], set()
    for tok in raw.split():
        clean = tok.replace("*", "").upper()
        if not clean:
            continue
        if "*" in tok:
            hi.add(len(words))
        words.append(clean)
    if not hi and words:
        hi.add(max(range(len(words)), key=lambda i: len(re.sub(r"\W", "", words[i]))))
    return words, hi


def partitions(n: int, k: int):
    """All ways to split n words into k consecutive non-empty lines."""
    for cuts in itertools.combinations(range(1, n), k - 1):
        b = (0,) + cuts + (n,)
        yield [list(range(b[i], b[i + 1])) for i in range(k)]


def layout_text(words, font_path, max_w, max_h, max_lines, condense):
    """Pick the line breaks that let the headline be as BIG as possible,
    preferring balanced lines (no lonely 'IS' on its own line)."""
    ref = ImageFont.truetype(font_path, 100)
    best = None
    for k in range(1, min(max_lines, len(words)) + 1):
        for lines in partitions(len(words), k):
            widths = [ref.getlength(" ".join(words[i] for i in ln)) * condense for ln in lines]
            size = min(100 * max_w / max(widths), max_h / (k * 1.05))
            balance = min(widths) / max(widths)
            score = size * (0.75 + 0.25 * balance)
            if best is None or score > best[0]:
                best = (score, int(min(size, 300)), lines)
    _, size, lines = best
    return ImageFont.truetype(font_path, max(size, 40)), lines


def render_line(words, idxs, hi, font, cfg) -> Image.Image:
    size = font.size
    stroke = max(6, size // 11)
    space = font.getlength(" ")
    total = sum(font.getlength(words[i]) for i in idxs) + space * (len(idxs) - 1)
    pad = stroke * 3
    asc, desc = font.getmetrics()
    w, h = int(total + pad * 2), int(asc + desc + pad * 2)

    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    shadow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d, ds = ImageDraw.Draw(layer), ImageDraw.Draw(shadow)
    x = pad
    for i in idxs:
        fill = hex_rgb(cfg["accent"]) if i in hi else hex_rgb(cfg["text"])
        ds.text((x + stroke * 0.6, pad + stroke * 0.9), words[i], font=font, fill=(0, 0, 0, 200),
                stroke_width=stroke, stroke_fill=(0, 0, 0, 200))
        d.text((x, pad), words[i], font=font, fill=fill + (255,),
               stroke_width=stroke, stroke_fill=hex_rgb(cfg["stroke"]) + (255,))
        x += font.getlength(words[i]) + space
    shadow = shadow.filter(ImageFilter.GaussianBlur(stroke * 0.8))
    out = Image.alpha_composite(shadow, layer)
    return out.resize((max(1, int(out.width * cfg["condense"])), out.height), Image.LANCZOS)


def draw_headline(canvas: Image.Image, title: str, font_path: str, cfg: dict, rng: random.Random) -> None:
    W, H = canvas.size
    words, hi = parse_title(title)
    if not words:
        return
    top, bottom = cfg["text_top"], cfg["text_bottom"]
    max_w, max_h = W * 0.86, H * (bottom - top)
    font, lines = layout_text(words, font_path, max_w, max_h * 0.92, cfg["max_lines"], cfg["condense"])
    imgs = [render_line(words, ln, hi, font, cfg) for ln in lines]
    # stretch shorter lines a little toward the widest (stacked-poster look)
    widest = max(i.width for i in imgs)
    scaled = []
    for im in imgs:
        k = min(widest / im.width, 1.18)
        scaled.append(im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS))
    overlap = int(font.size * 0.22)
    block_h = sum(i.height for i in scaled) - overlap * (len(scaled) - 1)
    block = Image.new("RGBA", (max(i.width for i in scaled), block_h), (0, 0, 0, 0))
    y = 0
    for im in scaled:
        block.alpha_composite(im, ((block.width - im.width) // 2, y))
        y += im.height - overlap
    block = block.rotate(rng.uniform(-3.5, -1.5), resample=Image.BICUBIC, expand=True)
    # final safety fit inside the text zone
    k = min(W * 0.96 / block.width, max_h * 1.05 / block.height, 1.0)
    if k < 1:
        block = block.resize((int(block.width * k), int(block.height * k)), Image.LANCZOS)
    cy = int(H * (top + bottom) / 2)
    canvas.alpha_composite(block, (W // 2 - block.width // 2, cy - block.height // 2))


def draw_badge(canvas: Image.Image, text: str, font_path: str, cfg: dict, rng: random.Random) -> None:
    W, H = canvas.size
    text = text.upper().strip()
    font = ImageFont.truetype(font_path, 92)
    tw = font.getlength(text)
    asc, desc = font.getmetrics()
    padx, pady = 46, 22
    w, h = int(tw + padx * 2), int(asc + desc + pady * 2)
    m = 30
    pill = Image.new("RGBA", (w + m * 2, h + m * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle((m + 8, m + 12, m + w + 8, m + h + 12), radius=h // 3, fill=(0, 0, 0, 150))
    pill = pill.filter(ImageFilter.GaussianBlur(8))
    d = ImageDraw.Draw(pill)
    d.rounded_rectangle((m, m, m + w, m + h), radius=h // 3, fill=hex_rgb(cfg["badge_bg"]) + (255,),
                        outline=(255, 255, 255, 255), width=8)
    d.text((m + padx, m + pady), text, font=font, fill=hex_rgb(cfg["badge_text"]) + (255,))
    pill = pill.resize((int(pill.width * cfg["condense"]), pill.height), Image.LANCZOS)
    pill = pill.rotate(rng.uniform(4, 8), resample=Image.BICUBIC, expand=True)
    canvas.alpha_composite(pill, (int(W * 0.06), int(H * 0.085)))


def draw_logo(canvas: Image.Image, cfg: dict) -> None:
    p = HERE / cfg["logo"]
    if not cfg.get("show_logo") or not p.exists():
        return
    W, H = canvas.size
    logo = Image.open(p).convert("RGBA")
    logo.thumbnail((int(W * 0.2), int(W * 0.2)), Image.LANCZOS)
    glow = Image.new("RGBA", (logo.width + 80, logo.height + 80), (0, 0, 0, 0))
    alpha = logo.split()[3].point(lambda a: 255 if a > 10 else 0)
    white = Image.new("RGBA", logo.size, (255, 255, 255, 255))
    glow.paste(white, (40, 40), alpha)
    glow = glow.filter(ImageFilter.MaxFilter(15)).filter(ImageFilter.GaussianBlur(6))
    glow.alpha_composite(logo, (40, 40))
    canvas.alpha_composite(glow, (W - glow.width - int(W * 0.02), int(H * 0.055)))


# ------------------------------------------------------------- assembling

def make_thumbnail(frame: Image.Image, title: str, badge: str | None, font_path: str, cfg: dict, seed: str) -> Image.Image:
    rng = random.Random(seed)
    W, H = cfg["width"], cfg["height"]
    base = fit_cover(frame, W, H)
    base = punch_up(base, cfg)
    base = vignette_and_shade(base, cfg)
    canvas = base.convert("RGBA")
    draw_logo(canvas, cfg)
    if badge:
        draw_badge(canvas, badge, font_path, cfg, rng)
    draw_headline(canvas, title, font_path, cfg, rng)
    return canvas.convert("RGB")


def title_from_name(stem: str) -> str:
    t = re.sub(r"[_\-]+", " ", stem)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def metadata_for(video: Path, titles: dict) -> tuple[str, str | None]:
    entry = titles.get(video.name) or titles.get(video.stem)
    if isinstance(entry, str):
        return entry, None
    if isinstance(entry, dict) and entry.get("title"):
        return entry["title"], entry.get("badge")
    side = video.with_suffix(".txt")
    if side.exists():
        lines = [ln.strip() for ln in side.read_text().splitlines() if ln.strip()]
        if lines:
            return lines[0], (lines[1] if len(lines) > 1 else None)
    return title_from_name(video.stem), None


def main() -> None:
    ap = argparse.ArgumentParser(description="Auto-generate 9:16 Shorts thumbnails.")
    ap.add_argument("input", help="a video file or a folder of videos")
    ap.add_argument("-o", "--out", default=None, help="output folder (default: <input>/thumbnails)")
    ap.add_argument("--title", help="headline (single-video mode); *word* = highlight")
    ap.add_argument("--badge", help='sticker text, e.g. "NEW", "LEAKED", "BREAKING"')
    ap.add_argument("--font", help="path to a .ttf/.otf to use")
    ap.add_argument("--samples", type=int, help="frames to sample per video")
    ap.add_argument("--force", action="store_true", help="re-make thumbnails that already exist")
    ap.add_argument("--keep-candidates", action="store_true", help="also save the top-5 frames per video")
    args = ap.parse_args()

    need("ffmpeg")
    need("ffprobe")
    cfg = load_config()
    if args.samples:
        cfg["samples"] = args.samples
    font_path = find_font(cfg, args.font)

    src = Path(args.input).expanduser().resolve()
    if src.is_dir():
        videos = sorted(p for p in src.iterdir() if p.suffix.lower() in VIDEO_EXTS)
        root = src
    elif src.is_file():
        videos, root = [src], src.parent
    else:
        raise SystemExit(f"not found: {src}")
    out_dir = Path(args.out).expanduser().resolve() if args.out else root / "thumbnails"
    out_dir.mkdir(parents=True, exist_ok=True)

    titles = {}
    if (root / "titles.json").exists():
        titles = json.loads((root / "titles.json").read_text())

    print(f"font: {font_path}")
    made = skipped = failed = 0
    for v in videos:
        dest = out_dir / f"{v.stem}.jpg"
        if dest.exists() and not args.force:
            skipped += 1
            continue
        title, badge = metadata_for(v, titles)
        if len(videos) == 1:
            title = args.title or title
            badge = args.badge or badge
        try:
            frame = best_frame(v, cfg["samples"], out_dir / "_candidates" if args.keep_candidates else None)
            thumb = make_thumbnail(frame, title, badge, font_path, cfg, seed=v.name)
            thumb.save(dest, "JPEG", quality=cfg["jpeg_quality"], optimize=True, progressive=True)
            made += 1
            print(f"✔ {v.name} -> {dest}  [{title}{' | ' + badge if badge else ''}]")
        except Exception as e:  # keep going on a bad file
            failed += 1
            print(f"✘ {v.name}: {e}", file=sys.stderr)
    print(f"\ndone: {made} made, {skipped} skipped (already exist, use --force), {failed} failed")


if __name__ == "__main__":
    main()
