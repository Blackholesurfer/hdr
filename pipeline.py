#!/usr/bin/env python3
"""End-to-end pipeline: enhance images, run fal.ai image-to-video, concat with crossfades.

Adapted from enhance_and_build.py + make_video.py to operate on arbitrary
input/output directories so it can be invoked per upload job from server.py.
"""

from pathlib import Path
import glob
import json
import subprocess
import urllib.request
from typing import Callable, Optional

from dotenv import load_dotenv
from PIL import Image, ImageEnhance, ImageOps, ImageFilter

load_dotenv(Path.home() / ".env")
import fal_client  # noqa: E402

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
PROMPTS_FILE = Path(__file__).parent / "prompts.json"

# Enhancement
BRIGHTNESS = 1.12
CONTRAST = 1.18
COLOR = 1.08
SHARPNESS = 1.15

# Video
TARGET_W, TARGET_H = 1280, 720
FADE_S = 1

def load_prompts() -> list[str]:
    """Load prompts from prompts.json. Falls back to a single generic prompt
    if the file is missing or malformed, so the pipeline never crashes for
    that reason."""
    try:
        data = json.loads(PROMPTS_FILE.read_text(encoding="utf-8"))
        prompts = [p for p in data.get("prompts", []) if isinstance(p, str) and p.strip()]
        if prompts:
            return prompts
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return [
        "Cinematic editorial image-to-video shot. Maintain composition, white balance, and architectural detail. Soft directional light."
    ]


def save_prompts(prompts: list[str]) -> None:
    PROMPTS_FILE.write_text(
        json.dumps({"prompts": prompts}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


StatusFn = Callable[[str, Optional[dict]], None]


def _enhance_one(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        if im.mode != "RGB":
            im = im.convert("RGB")
        im = ImageEnhance.Brightness(im).enhance(BRIGHTNESS)
        im = ImageEnhance.Contrast(im).enhance(CONTRAST)
        im = ImageEnhance.Color(im).enhance(COLOR)
        im = ImageEnhance.Sharpness(im).enhance(SHARPNESS)
        im = im.filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        im.save(dst.with_suffix(".jpg"), format="JPEG", quality=92, optimize=True)


def _probe_duration(path: str) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)


def _make_boomerang(src: Path, dst: Path) -> None:
    subprocess.run([
        "ffmpeg", "-y", "-i", str(src),
        "-filter_complex",
        "[0:v]split[a][b];[b]reverse[r];[a][r]concat=n=2:v=1:a=0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "fast",
        "-movflags", "+faststart",
        str(dst),
    ], check=True, capture_output=True)


def run_pipeline(raw_dir: Path, job_dir: Path, status: StatusFn) -> Path:
    """Run enhance + image-to-video + concat. Returns the final boomerang video path."""
    enh_dir = job_dir / "enhanced"
    clips_dir = job_dir / "clips"
    enh_dir.mkdir(parents=True, exist_ok=True)
    clips_dir.mkdir(parents=True, exist_ok=True)

    raws = sorted([p for p in raw_dir.iterdir() if p.suffix.lower() in IMAGE_EXTS])
    if not raws:
        raise RuntimeError("No images to process.")

    total = len(raws)
    enhanced_paths: list[Path] = []

    for i, src in enumerate(raws, start=1):
        status("enhancing", {"step": i, "total": total, "name": src.name})
        out = enh_dir / Path(src.name).with_suffix(".jpg").name
        _enhance_one(src, out)
        enhanced_paths.append(out)

    clip_files: list[str] = []
    prompts = load_prompts()
    for i, img_path in enumerate(enhanced_paths):
        clip_path = clips_dir / f"clip_{i:03d}.mp4"
        if clip_path.exists():
            clip_files.append(str(clip_path))
            continue

        status("uploading", {"step": i + 1, "total": len(enhanced_paths), "name": img_path.name})
        image_url = fal_client.upload_file(str(img_path))

        status("generating", {"step": i + 1, "total": len(enhanced_paths), "name": img_path.name})
        try:
            result = fal_client.run(
                "fal-ai/kling-video/v1.6/standard/image-to-video",
                arguments={
                    "prompt": prompts[i % len(prompts)],
                    "image_url": image_url,
                    "duration": "10",
                    "aspect_ratio": "16:9",
                },
            )
        except fal_client.client.FalClientHTTPError as e:
            if "content_policy_violation" in str(e):
                status("skipped", {"step": i + 1, "total": len(enhanced_paths), "name": img_path.name})
                continue
            raise

        video_url = result["video"]["url"]
        status("downloading", {"step": i + 1, "total": len(enhanced_paths), "name": img_path.name})
        urllib.request.urlretrieve(video_url, clip_path)
        clip_files.append(str(clip_path))

    if not clip_files:
        raise RuntimeError("No clips generated (all skipped).")

    status("combining", {"clips": len(clip_files)})
    durations = [_probe_duration(c) for c in clip_files]

    n = len(clip_files)
    inputs: list[str] = []
    for clip in clip_files:
        inputs += ["-i", clip]

    filter_parts = []
    for i in range(n):
        filter_parts.append(
            f"[{i}:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
            f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[n{i}]"
        )

    if n == 1:
        filter_parts.append("[n0]copy[vout]")
    else:
        chain_dur = durations[0]
        last = "[n0]"
        for i in range(1, n):
            offset = chain_dur - FADE_S
            out = f"[v{i}]" if i < n - 1 else "[vout]"
            filter_parts.append(
                f"{last}[n{i}]xfade=transition=fade:duration={FADE_S}:offset={offset:.3f}{out}"
            )
            last = f"[v{i}]"
            chain_dur += durations[i] - FADE_S

    filter_str = ";".join(filter_parts)
    final_path = job_dir / "final_video.mp4"

    subprocess.run([
        "ffmpeg", "-y",
        *inputs,
        "-filter_complex", filter_str,
        "-map", "[vout]",
        "-c:v", "libx264", "-crf", "18", "-preset", "fast",
        "-pix_fmt", "yuv420p",
        str(final_path),
    ], check=True, capture_output=True)

    status("boomerang", None)
    pp_path = job_dir / "final_video_pp.mp4"
    _make_boomerang(final_path, pp_path)

    return pp_path
