#!/usr/bin/env python3.14
from pathlib import Path
import html
from PIL import Image, ImageEnhance, ImageOps, ImageFilter, ExifTags
import json
from typing import Any, Dict, Optional

# Trainer: 
BASE_DIR = Path("/Users/danielhudsky/lab/hackathon")
IMG_DIR  = BASE_DIR / "qualifiedimages"
OUT_DIR  = BASE_DIR / "images_enhanced"
OUT_HTML = BASE_DIR / "index.html"
META_FILE = BASE_DIR / "training_metadata.json"

def load_training_metadata(path: Path) -> Dict[str, Dict[str, Any]]:
    """
    Returns a dict keyed by filename -> metadata record.
    Supports:
      - JSON array of objects
      - JSONL (one JSON object per line)
    """
    if not path.exists():
        return {}

    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return {}

    records = []
    try:
        data = json.loads(text)
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            # if someone stored a dict wrapper, try common pattern
            # e.g. {"items":[...]}
            if "items" in data and isinstance(data["items"], list):
                records = data["items"]
            else:
                records = [data]
    except json.JSONDecodeError:
        # Try JSONL
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    idx: Dict[str, Dict[str, Any]] = {}
    for r in records:
        if not isinstance(r, dict):
            continue
        # index both filenames so either can match src.name
        for key in ("original", "generated"):
            fn = r.get(key)
            if isinstance(fn, str) and fn:
                idx[fn] = r
    return idx

BASE_DIR = Path("/Users/danielhudsky/lab/hackathon")
IMG_DIR  = BASE_DIR / "qualifiedimages"
OUT_DIR  = BASE_DIR / "images_enhanced"
OUT_HTML = BASE_DIR / "index.html"



IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Server-side (baked) enhancement knobs
BRIGHTNESS = 1.12
CONTRAST   = 1.18
COLOR      = 1.08   # saturation
SHARPNESS  = 1.15

# Lens distortion correction
APPLY_LENS_CORRECTION = True

# Optional deps (only used if installed)
try:
    import numpy as np
    import cv2
    import lensfunpy
except Exception:
    np = cv2 = lensfunpy = None


def _exif_dict(im: Image.Image) -> dict:
    """
    Returns EXIF as a human-keyed dict when possible.
    """
    out = {}
    try:
        ex = im.getexif()
        if not ex:
            return out
        tagmap = {v: k for k, v in ExifTags.TAGS.items()}
        for k, v in ex.items():
            name = ExifTags.TAGS.get(k, k)
            out[name] = v
    except Exception:
        pass
    return out


def _ratio_to_float(x):
    # EXIF rationals can be tuples or PIL Rational
    try:
        if isinstance(x, tuple) and len(x) == 2:
            return float(x[0]) / float(x[1]) if x[1] else None
        return float(x)
    except Exception:
        return None


def correct_lens_distortion(im: Image.Image, meta: Optional[dict] = None) -> Image.Image:
    if not APPLY_LENS_CORRECTION:
        return im
    if np is None or cv2 is None or lensfunpy is None:
        return im

    ex = _exif_dict(im)

    # Prefer JSON overrides if provided, fallback to EXIF
    make  = (meta or {}).get("camera_make")  or ex.get("Make")
    model = (meta or {}).get("camera_model") or ex.get("Model")
    lens  = (meta or {}).get("lens_model")   or ex.get("LensModel") or ex.get("Lens")

    focal = None
    if meta and meta.get("focal_length"):
        # meta focal_length looks like "16.0 mm"
        try:
            focal = float(str(meta["focal_length"]).replace("mm", "").strip())
        except Exception:
            focal = None
    if focal is None:
        focal = _ratio_to_float(ex.get("FocalLength"))

    aperture = 0.0
    if meta and meta.get("f_number") is not None:
        try:
            aperture = float(meta["f_number"])
        except Exception:
            aperture = 0.0

    if not make or not model or not focal:
        return im

    make = str(make).strip()
    model = str(model).strip()
    lens = str(lens).strip() if lens else None

    width, height = im.size

    try:
        db = lensfunpy.Database()
        cams = db.find_cameras(make, model)
        if not cams:
            return im
        cam = cams[0]

        if not lens:
            return im

        lenses = db.find_lenses(cam, lens)
        if not lenses:
            return im
        lf_lens = lenses[0]

        mod = lensfunpy.Modifier(lf_lens, cam.crop_factor, width, height)
        mod.initialize(focal, aperture=aperture, distance=0.0)

        coords = mod.apply_geometry_distortion()
        map_x = coords[:, :, 0].astype(np.float32)
        map_y = coords[:, :, 1].astype(np.float32)

        arr = np.array(im)
        corrected = cv2.remap(arr, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(corrected)
    except Exception:
        return im

    ex = _exif_dict(im)

    make  = ex.get("Make")
    model = ex.get("Model")
    lens  = ex.get("LensModel") or ex.get("Lens")  # some cameras use "Lens"
    focal = _ratio_to_float(ex.get("FocalLength"))

    # Need at least camera make/model + focal length to have a decent shot at a match
    if not make or not model or not focal:
        return im

    # Normalize strings (Lensfun matching is picky)
    make = str(make).strip()
    model = str(model).strip()
    lens = str(lens).strip() if lens else None

    width, height = im.size

    try:
        db = lensfunpy.Database()
        cams = db.find_cameras(make, model)
        if not cams:
            return im
        cam = cams[0]

        # If we have lens model, use it; else try any lens that fits the camera
        if lens:
            lenses = db.find_lenses(cam, lens)
        else:
            # If we don't know the lens, you *can* try all, but that’s risky.
            return im

        if not lenses:
            return im
        lf_lens = lenses[0]

        # Modifier creates mapping for geometric correction.
        # crop_factor is important for correct geometry.
        mod = lensfunpy.Modifier(lf_lens, cam.crop_factor, width, height)
        # aperture and distance are optional; set to 0 if unknown
        mod.initialize(focal, aperture=0.0, distance=0.0)

        # Lensfun gives a coordinate mapping; OpenCV remaps pixels accordingly.
        # coords shape: (h, w, 2) float32, with x/y source coordinates
        coords = mod.apply_geometry_distortion()
        map_x = coords[:, :, 0].astype(np.float32)
        map_y = coords[:, :, 1].astype(np.float32)

        arr = np.array(im)  # RGB
        corrected = cv2.remap(arr, map_x, map_y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
        return Image.fromarray(corrected)

    except Exception:
        # If anything goes wrong (no DB, bad match, etc.) just keep original.
        return im


def enhance_image(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)

        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        if im.mode == "RGBA":
            im = im.convert("RGB")

        # NEW: de-lens (distortion correction) before enhancements/sharpening
        im = correct_lens_distortion(im)

        im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
        im = ImageEnhance.Contrast(im).enhance(CONTRAST)
        im = ImageEnhance.Color(im).enhance(COLOR)
        im = ImageEnhance.Sharpness(im).enhance(SHARPNESS)

        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))

        dst = dst.with_suffix(".jpg")
        im.save(dst, format="JPEG", quality=92, optimize=True)


def main():
    if not IMG_DIR.is_dir():
        raise SystemExit(f"Missing: {IMG_DIR}")

    imgs = sorted([p for p in IMG_DIR.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTS])
    if not imgs:
        raise SystemExit("No images found")

    cards = []
    for i, src in enumerate(imgs, start=1):
        rel_src = src.relative_to(BASE_DIR)          # images/...
        rel_under_images = src.relative_to(IMG_DIR)  # filename under images/

        dst = OUT_DIR / rel_under_images
        print(f"Enhancing {src.name}")
        try:
            enhance_image(src, dst)
        except Exception as e:
            print(f"Skipping {src}: {e}")
            continue

        rel_dst = (Path("images_enhanced") / rel_under_images).with_suffix(".jpg")
        img_id = html.escape(rel_under_images.as_posix())

        cards.append(f"""
        <div class="card">
          <div class="row">
            <div>
              <div class="label">Original</div>
              <img src="{html.escape(rel_src.as_posix())}" loading="lazy">
            </div>
            <div>
              <div class="label">Enhanced (preview adjustable)</div>
              <img class="enhanced" data-image-id="{img_id}" src="{html.escape(rel_dst.as_posix())}" loading="lazy">
              <div class="perimg">
                <span class="pill">Per-image:</span>
                <button class="smallbtn" onclick="useGlobalFor('{img_id}')">Use global</button>
                <button class="smallbtn" onclick="resetImage('{img_id}')">Reset image</button>
              </div>
            </div>
          </div>
          <div class="name">{img_id}</div>
        </div>
        """)

    # (rest of your HTML template stays exactly the same)
    html_template = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Enhanced Gallery</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
/* ... unchanged ... */
</style>
</head>
<body>
<header>
  <!-- ... unchanged ... -->
</header>

{CARDS}

<script>
/* ... unchanged ... */
</script>
</body>
</html>
"""
    OUT_HTML.write_text(html_template.replace("{CARDS}", "".join(cards)), encoding="utf-8")
    print(f"DONE: wrote {OUT_HTML} and enhanced images to {OUT_DIR}")

if __name__ == "__main__":
    main()
