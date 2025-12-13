#!/usr/bin/env python3.12
from pathlib import Path
import html
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

BASE_DIR = Path("/var/opt/www")
IMG_DIR  = BASE_DIR / "images"
OUT_DIR  = BASE_DIR / "images_enhanced"
OUT_HTML = BASE_DIR / "index.html"

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}

# Server-side (baked) enhancement knobs
BRIGHTNESS = 1.12
CONTRAST   = 1.18
COLOR      = 1.08   # saturation
SHARPNESS  = 1.15

def enhance_image(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)

        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGB")
        if im.mode == "RGBA":
            im = im.convert("RGB")

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

    html_template = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Enhanced Gallery</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
body { background:#111; color:#ddd; font-family:Arial; margin:0; }
header { padding:14px 18px; border-bottom:1px solid #333; position:sticky; top:0; background:#111; z-index:10; }
.controls { display:flex; flex-wrap:wrap; gap:12px 18px; align-items:end; margin-top:12px; }
.control { display:flex; flex-direction:column; gap:6px; min-width:220px; }
label { color:#aaa; font-size:12px; }
input[type="range"] { width:220px; }
.smallbtn { background:#1a1a1a; border:1px solid #444; color:#ddd; padding:8px 10px; border-radius:8px; cursor:pointer; }
.smallbtn:hover { border-color:#666; }
.note { color:#aaa; font-size:12px; margin-top:6px; }

.card { margin:18px; padding-bottom:18px; border-bottom:1px solid #333; }
.row { display:grid; grid-template-columns:1fr 1fr; gap:12px; }
img { width:100%; max-height:320px; object-fit:cover; border:1px solid #444; display:block; }
.label { color:#aaa; font-size:13px; margin:6px 0; }
.name { color:#9fd3ff; font-size:13px; margin-top:10px; }

.perimg { display:flex; gap:10px; align-items:center; margin-top:10px; flex-wrap:wrap; }
.perimg .pill { font-size:12px; color:#aaa; }
</style>
</head>
<body>

<header>
  <div style="display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap;">
    <div>
      <div><strong>Gallery Controls</strong></div>
      <div class="note">Sliders adjust preview only. Settings persist in this browser.</div>
    </div>
    <div style="display:flex; gap:10px; align-items:center;">
      <button class="smallbtn" onclick="resetAll()">Reset all</button>
      <button class="smallbtn" onclick="saveAll()">Save settings</button>
    </div>
  </div>

  <div class="controls">
    <div class="control">
      <label>Brightness: <span id="bVal"></span></label>
      <input id="brightness" type="range" min="0.50" max="1.80" step="0.01" value="1.00">
    </div>
    <div class="control">
      <label>Contrast: <span id="cVal"></span></label>
      <input id="contrast" type="range" min="0.50" max="2.20" step="0.01" value="1.00">
    </div>
    <div class="control">
      <label>Saturation: <span id="sVal"></span></label>
      <input id="saturation" type="range" min="0.00" max="2.50" step="0.01" value="1.00">
    </div>
    <div class="control">
      <label>“Crisp” (simulated): <span id="kVal"></span></label>
      <input id="crisp" type="range" min="0.80" max="1.60" step="0.01" value="1.00">
    </div>
  </div>
</header>

{CARDS}

<script>
const defaults = { brightness: 1.00, contrast: 1.00, saturation: 1.00, crisp: 1.00 };

const sliders = {
  brightness: document.getElementById("brightness"),
  contrast: document.getElementById("contrast"),
  saturation: document.getElementById("saturation"),
  crisp: document.getElementById("crisp"),
};

const labels = {
  bVal: document.getElementById("bVal"),
  cVal: document.getElementById("cVal"),
  sVal: document.getElementById("sVal"),
  kVal: document.getElementById("kVal"),
};

function fmt(x) { return Number(x).toFixed(2); }

function getGlobal() {
  return {
    brightness: Number(sliders.brightness.value),
    contrast: Number(sliders.contrast.value),
    saturation: Number(sliders.saturation.value),
    crisp: Number(sliders.crisp.value),
  };
}

function setGlobal(v) {
  sliders.brightness.value = v.brightness;
  sliders.contrast.value = v.contrast;
  sliders.saturation.value = v.saturation;
  sliders.crisp.value = v.crisp;
  updateGlobalLabels();
}

function updateGlobalLabels() {
  const g = getGlobal();
  labels.bVal.textContent = fmt(g.brightness);
  labels.cVal.textContent = fmt(g.contrast);
  labels.sVal.textContent = fmt(g.saturation);
  labels.kVal.textContent = fmt(g.crisp);
}

function cssFilterFrom(v) {
  // Crisp simulated with drop-shadow (subtle) + extra contrast
  const extraContrast = v.crisp;
  const shadow = (v.crisp > 1.0) ? ` drop-shadow(0 0 ${((v.crisp-1.0)*1.2).toFixed(2)}px rgba(255,255,255,0.15))` : "";
  return `brightness(${v.brightness}) contrast(${(v.contrast * extraContrast).toFixed(3)}) saturate(${v.saturation})${shadow}`;
}

function loadGlobal() {
  try {
    const raw = localStorage.getItem("globalFilters");
    return raw ? JSON.parse(raw) : null;
  } catch(e) { return null; }
}

function loadPerImage(id) {
  try {
    const raw = localStorage.getItem("perImageFilters");
    if (!raw) return null;
    const all = JSON.parse(raw);
    return all[id] ?? null;
  } catch(e) { return null; }
}

function savePerImage(id, val) {
  let all = {};
  try {
    const raw = localStorage.getItem("perImageFilters");
    all = raw ? JSON.parse(raw) : {};
  } catch(e) { all = {}; }
  all[id] = val;
  localStorage.setItem("perImageFilters", JSON.stringify(all));
}

function resetImage(id) {
  let all = {};
  try {
    const raw = localStorage.getItem("perImageFilters");
    all = raw ? JSON.parse(raw) : {};
  } catch(e) { all = {}; }
  delete all[id];
  localStorage.setItem("perImageFilters", JSON.stringify(all));
  applyAll();
}

function useGlobalFor(id) {
  savePerImage(id, getGlobal());
  applyAll();
}

function applyAll() {
  const g = getGlobal();
  document.querySelectorAll("img.enhanced").forEach(img => {
    const id = img.getAttribute("data-image-id");
    const per = loadPerImage(id);
    const v = per ?? g;
    img.style.filter = cssFilterFrom(v);
  });
}

function saveAll() {
  localStorage.setItem("globalFilters", JSON.stringify(getGlobal()));
  alert("Saved.");
}

function resetAll() {
  localStorage.removeItem("globalFilters");
  localStorage.removeItem("perImageFilters");
  setGlobal(defaults);
  applyAll();
}

window.resetAll = resetAll;
window.saveAll = saveAll;
window.useGlobalFor = useGlobalFor;
window.resetImage = resetImage;

Object.values(sliders).forEach(s => {
  s.addEventListener("input", () => {
    updateGlobalLabels();
    applyAll();
  });
});

setGlobal(loadGlobal() ?? defaults);
applyAll();
</script>

</body>
</html>
"""

    OUT_HTML.write_text(html_template.replace("{CARDS}", "".join(cards)), encoding="utf-8")
    print(f"DONE: wrote {OUT_HTML} and enhanced images to {OUT_DIR}")

if __name__ == "__main__":
    main()

