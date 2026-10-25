#!/usr/bin/env python3
"""
StampBatch — batch photo watermarking (text or logo), 100% local.

Pipeline:
  1. Read every supported photo in the input folder (never modified).
  2. Composite a text or logo watermark onto a copy — nine-grid position,
     opacity and relative size are configurable; an optional tiled mode
     repeats the mark across the whole frame. Platform presets only tune
     the recommended relative size and margin for that platform.
  3. Write results to a separate output folder, originals untouched.
  4. Re-check every output: it must reopen, its pixel dimensions must
     match the original exactly, and pixels inside the watermark
     area must actually differ from the original (i.e. the mark is really
     composited, not silently dropped). Results land in stamp_report.md.

StampBatch only watermarks. It never resizes, crops, renames or converts
your photos — output dimensions always equal input dimensions.

Local only. No network access. Built on Pillow (HPND licence).
"""
import hashlib
import math
import os
import sys

from PIL import Image, ImageChops, ImageDraw, ImageFont

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

POSITIONS = [
    "top-left", "top-center", "top-right",
    "center-left", "center", "center-right",
    "bottom-left", "bottom-center", "bottom-right",
]

# A preset only advises the watermark's relative width and margin.
# It never changes the photo itself — output size always equals input size.
PRESETS = {
    "generic":   {"size_ratio": 0.22, "margin_ratio": 0.03,
                  "note": "Balanced default for web and client delivery."},
    "etsy":      {"size_ratio": 0.18, "margin_ratio": 0.05,
                  "note": "Etsy listing photos: smaller mark, wider margin so "
                          "thumbnail crops stay clear of it."},
    "instagram": {"size_ratio": 0.25, "margin_ratio": 0.05,
                  "note": "Instagram feed posts are often re-shared; a larger "
                          "mark with a safe margin survives screenshots."},
}

_HERE = os.path.dirname(os.path.abspath(__file__))


def _font_candidates():
    roots = [_HERE, os.getcwd()]
    if getattr(sys, "frozen", False):  # PyInstaller bundle
        roots += [getattr(sys, "_MEIPASS", _HERE),
                  os.path.join(os.path.dirname(sys.executable), "_internal"),
                  os.path.dirname(sys.executable)]
    paths = []
    for root in roots:
        for sub in ("assets", os.path.join("_internal", "assets")):
            for name in ("DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
                paths.append(os.path.join(root, sub, name))
    paths += ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf"]
    return paths


def _load_font(px):
    for cand in _font_candidates():
        try:
            return ImageFont.truetype(cand, max(8, int(px)))
        except Exception:
            continue
    return ImageFont.load_default()


def render_text_mark(text, font_px, color=(255, 255, 255), pad_ratio=0.35):
    """Render a text watermark as an RGBA tile (alpha filled at 255;
    the caller's opacity is applied when compositing)."""
    font = _load_font(font_px)
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    bbox = probe.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    pad = max(2, int(font_px * pad_ratio))
    tile = Image.new("RGBA", (tw + 2 * pad, th + 2 * pad), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    # soft shadow so the mark stays readable on busy photos
    shadow = (0, 0, 0) if color == (255, 255, 255) else (255, 255, 255)
    d.text((pad - bbox[0] + max(1, font_px // 40), pad - bbox[1] + max(1, font_px // 40)),
           text, font=font, fill=shadow + (110,))
    d.text((pad - bbox[0], pad - bbox[1]), text, font=font, fill=color + (255,))
    return tile


def render_text_tile(text, color_name, target_w):
    """Render a text watermark at (approximately) its final pixel width.

    Rendering once at a large size and downscaling would smear thin glyph
    strokes into near-invisibility on small photos, so the text is drawn
    at the size it will actually appear at."""
    color = (0, 0, 0) if color_name == "black" else (255, 255, 255)
    probe = render_text_mark(text, 100, color)
    font_px = max(8, int(100 * target_w / max(1, probe.width)))
    return render_text_mark(text, font_px, color)


def load_logo(path):
    logo = Image.open(path)
    return logo.convert("RGBA")


def _scale_to_width(mark, target_w):
    if target_w <= 0 or mark.width == target_w:
        return mark
    ratio = target_w / mark.width
    return mark.resize((max(1, int(mark.width * ratio)),
                        max(1, int(mark.height * ratio))), Image.LANCZOS)


def _with_opacity(mark, opacity):
    """Return a copy of the mark with its alpha scaled to `opacity` (0-255)."""
    if opacity >= 255:
        return mark
    m = mark.copy()
    alpha = m.getchannel("A").point(lambda a: a * opacity // 255)
    m.putalpha(alpha)
    return m


def _anchor(position, W, H, w, h, margin):
    col = 0 if position.endswith("left") else 2 if position.endswith("right") else 1
    row = 0 if position.startswith("top") else 2 if position.startswith("bottom") else 1
    xs = [margin, (W - w) // 2, W - w - margin]
    ys = [margin, (H - h) // 2, H - h - margin]
    return xs[col], ys[row]


def apply_mark(base_rgba, mark, position, size_ratio, margin_ratio, opacity):
    """Composite a single mark. Returns (image, bbox) where bbox is the
    (x0, y0, x1, y1) region the mark occupies on the output."""
    W, H = base_rgba.size
    target_w = max(8, int(W * size_ratio))
    m = _with_opacity(_scale_to_width(mark, target_w), opacity)
    margin = int(min(W, H) * margin_ratio)
    x, y = _anchor(position, W, H, m.width, m.height, margin)
    out = base_rgba.copy()
    out.alpha_composite(m, (x, y))
    return out, (x, y, x + m.width, y + m.height)


def apply_tile(base_rgba, mark, size_ratio, opacity, gap_ratio=0.6, angle=0):
    """Repeat the mark across the whole frame. Returns the composited image."""
    W, H = base_rgba.size
    target_w = max(8, int(W * size_ratio))
    m = _with_opacity(_scale_to_width(mark, target_w), opacity)
    gap = max(4, int(m.width * gap_ratio))
    layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    step_x, step_y = m.width + gap, m.height + gap
    rows = math.ceil(H / step_y) + 1
    for r in range(rows):
        offset = (m.width // 2) if r % 2 else 0  # brick layout
        for cx in range(-1, math.ceil(W / step_x) + 1):
            layer.alpha_composite(m, (cx * step_x + offset, r * step_y))
    if angle:
        layer = layer.rotate(angle, resample=Image.BICUBIC, center=(W // 2, H // 2))
    out = base_rgba.copy()
    out.alpha_composite(layer, (0, 0))
    return out


def _sample_changed(orig_rgba, out_rgba, region, step=None):
    """Exact fraction of pixels in `region` that differ between the two
    images (per-channel delta > 8 on any of R/G/B — roughly a 3% change,
    below which a mark is not meaningfully visible). Computed over every
    pixel via ImageChops, so even a small mark on a small photo is judged
    on full evidence, not on a sparse sample grid."""
    x0, y0, x1, y1 = region
    x1, y1 = min(x1, orig_rgba.width), min(y1, orig_rgba.height)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    box = (x0, y0, x1, y1)
    diff = ImageChops.difference(orig_rgba.crop(box), out_rgba.crop(box)).convert("RGB")
    r, g, b = diff.split()
    strongest = ImageChops.lighter(ImageChops.lighter(r, g), b)
    hist = strongest.histogram()
    total = (x1 - x0) * (y1 - y0)
    return sum(hist[9:]) / total if total else 0.0


def verify_output(orig_path, out_path, bbox=None, tiled=False):
    """Re-open the output and prove the watermark landed:
    - output opens as an image;
    - pixel dimensions equal the original's;
    - pixels differ from the original where the mark was placed
      (single mode: inside the mark bbox; tiled mode: across the frame).
    Returns (ok, detail_string)."""
    try:
        orig = Image.open(orig_path).convert("RGBA")
    except Exception as e:
        return False, f"original unreadable: {e}"
    try:
        out = Image.open(out_path)
        out.load()
        out = out.convert("RGBA")
    except Exception as e:
        return False, f"output does not reopen: {e}"
    if out.size != orig.size:
        return False, f"size changed: {orig.size} -> {out.size}"
    if tiled:
        frac = _sample_changed(orig, out, (0, 0, orig.width, orig.height))
        where = "across the frame (tiled)"
    else:
        frac = _sample_changed(orig, out, bbox or (0, 0, orig.width, orig.height))
        where = "inside the watermark area"
    if frac < 0.02:
        return False, f"only {frac:.1%} of pixels {where} differ — mark may be missing"
    return True, f"size {out.size[0]}x{out.size[1]} matches; {frac:.0%} of pixels {where} differ from the original"


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def process_folder(input_dir, output_dir, config):
    """Watermark every supported photo in input_dir into output_dir, then
    verify each output. Writes stamp_report.md. Returns a summary dict.
    config keys: mode ('text'|'logo'), text, logo_path, color ('white'|'black'),
    position (nine-grid), opacity (0-255), size_ratio, margin_ratio,
    preset (name or None), tile (bool), tile_angle (degrees)."""
    os.makedirs(output_dir, exist_ok=True)
    preset = PRESETS.get(config.get("preset") or "generic", PRESETS["generic"])
    size_ratio = float(config.get("size_ratio") or preset["size_ratio"])
    margin_ratio = float(config.get("margin_ratio") or preset["margin_ratio"])
    opacity = int(config.get("opacity", 170))
    position = config.get("position", "bottom-right")
    tile = bool(config.get("tile"))
    logo_mark = None
    if config.get("mode") == "logo":
        if not config.get("logo_path"):
            raise ValueError("logo mode needs a logo image file")
        logo_mark = load_logo(config["logo_path"])
    elif not (config.get("text") or "").strip():
        raise ValueError("text mode needs watermark text")

    names = sorted(n for n in os.listdir(input_dir)
                   if os.path.splitext(n)[1].lower() in SUPPORTED_EXTS
                   and os.path.isfile(os.path.join(input_dir, n)))
    results, failures = [], []
    for name in names:
        src = os.path.join(input_dir, name)
        dst = os.path.join(output_dir, name)
        try:
            base = Image.open(src).convert("RGBA")
            if logo_mark is not None:
                mark = logo_mark
            else:  # text: render at this photo's final mark width
                mark = render_text_tile(config["text"].strip(), config.get("color"),
                                        max(8, int(base.width * size_ratio)))
            if tile:
                out = apply_tile(base, mark, size_ratio, opacity,
                                 angle=int(config.get("tile_angle", 0)))
                bbox = None
            else:
                out, bbox = apply_mark(base, mark, position, size_ratio,
                                       margin_ratio, opacity)
            ext = os.path.splitext(name)[1].lower()
            if ext in (".jpg", ".jpeg"):
                out.convert("RGB").save(dst, "JPEG", quality=92)
            elif ext == ".webp":
                out.save(dst, "WEBP", quality=92)
            elif ext in (".tif", ".tiff"):
                out.convert("RGB").save(dst, "TIFF")
            elif ext == ".bmp":
                out.convert("RGB").save(dst, "BMP")
            else:
                out.save(dst, "PNG")
            ok, detail = verify_output(src, dst, bbox=bbox, tiled=tile)
            (results if ok else failures).append((name, detail))
        except Exception as e:
            failures.append((name, f"processing failed: {e}"))

    mode_desc = ("logo " + os.path.basename(config.get("logo_path") or "")) if config.get("mode") == "logo" \
        else f"text '{config.get('text', '')}'"
    lines = ["# StampBatch — watermark & re-check report", "",
             f"Input folder: {input_dir}",
             f"Watermark: {mode_desc} · {'tiled' if tile else 'position ' + position} · "
             f"opacity {opacity}/255 · size {size_ratio:.0%} of photo width · "
             f"preset {config.get('preset') or 'generic'}", "",
             "## Summary",
             f"- Photos found: {len(names)}",
             f"- Watermarked & verified: {len(results)}",
             f"- Failed verification: {len(failures)}", "",
             "## Per-photo re-check"]
    lines += [f"- [OK] {n} — {d}" for n, d in results]
    lines += [f"- [FAIL] {n} — {d}" for n, d in failures]
    lines += ["", "## Notes",
              "- Verification re-opens each output, confirms its pixel dimensions are "
              "identical to the original, and compares pixels where the watermark was "
              "composited to confirm the mark is really there.",
              "- Originals are never modified; outputs are written to a separate folder.",
              "- StampBatch only watermarks — it does not resize, crop, rename or "
              "convert your photos."]
    report_path = os.path.join(output_dir, "stamp_report.md")
    with open(report_path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return {"found": len(names), "ok": len(results), "failed": len(failures),
            "results": results, "failures": failures, "report_path": report_path}


def main(argv):
    import argparse
    p = argparse.ArgumentParser(prog="stamp_batch",
                                description="Batch-watermark photos locally (text or logo).")
    p.add_argument("input_dir")
    p.add_argument("output_dir")
    p.add_argument("--text", default="", help="watermark text (text mode)")
    p.add_argument("--logo", default="", help="logo image path (logo mode)")
    p.add_argument("--color", choices=["white", "black"], default="white")
    p.add_argument("--position", choices=POSITIONS, default="bottom-right")
    p.add_argument("--opacity", type=int, default=170, help="0-255")
    p.add_argument("--size", type=float, default=0.0,
                   help="watermark width as a fraction of photo width (0 = preset default)")
    p.add_argument("--margin", type=float, default=0.0,
                   help="margin as a fraction of the shorter side (0 = preset default)")
    p.add_argument("--preset", choices=sorted(PRESETS), default="generic")
    p.add_argument("--tile", action="store_true", help="repeat the watermark across the frame")
    p.add_argument("--tile-angle", type=int, default=0)
    a = p.parse_args(argv[1:])
    config = {"mode": "logo" if a.logo else "text", "text": a.text,
              "logo_path": a.logo, "color": a.color, "position": a.position,
              "opacity": a.opacity, "size_ratio": a.size or None,
              "margin_ratio": a.margin or None, "preset": a.preset,
              "tile": a.tile, "tile_angle": a.tile_angle}
    s = process_folder(a.input_dir, a.output_dir, config)
    print(f"found={s['found']} ok={s['ok']} failed={s['failed']} report={s['report_path']}")
    return 0 if s["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
