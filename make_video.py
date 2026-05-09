#!/usr/bin/env python3
import os
import glob
import subprocess
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path.home() / ".env")

import fal_client

IMAGES_DIR = Path(__file__).parent / "images"
OUTPUT_DIR = Path(__file__).parent / "video_clips"
FINAL_VIDEO = Path(__file__).parent / "final_video.mp4"

OUTPUT_DIR.mkdir(exist_ok=True)

PROMPTS = [
    "Transform this photo into a cinematic editorial image with harsh, directional shadows and crisp light shaping. Correct any perspective distortion—ensure vertical lines are truly vertical and horizontal lines are level. Maintain the exact scene composition after correction and preserve the original white balance. Balance overall exposure with intention: raise interior midtones subtly for improved readability and presence, while preserving deep, sculpted shadow structure and strong contrast. The interior should feel brighter and more intentional, not flat or evenly lit—shadows must remain graphic, directional, and editorial. Highlights should stay controlled and natural. Apply intentional, filmic window pulls that reveal deep, rich exterior views—preserve sky density, environmental color, and contrast beyond the glass. Exterior scenes should feel dimensional and weighty, never washed out or pastel. Window highlights must roll off smoothly with realistic falloff; avoid haloing, edge glow, or global tonal compression. Do not flatten contrast or lift blacks globally. Window recovery should feel localized, natural, and optically believable—similar to a well-exposed negative rather than HDR processing. Preserve all architectural and interior details. The scene should feel well-lit yet moody, polished and cinematic. Derive all lighting direction strictly from visible sources in the frame—windows, doors, architectural openings, and practical fixtures (lamps, sconces, pendants). Do not introduce light from walls or areas without logical entry points. Maintain strong tonal separation between interior shadows and exterior highlights; window views should read clear, saturated, and contrast-rich, while the interior retains depth, drama, and editorial punch.",
    "Generate a 50mm detail shot looking upward at the roofline with sharp architectural edges composed aesthetically against the sky. Sharp focus on roof edges with natural cloud formations in background. Frame the composition to emphasize the geometric shapes and lines of the roofline in a visually compelling arrangement. Preserve exact architecture, materials, and building details.",
    "Transform this photo into a cinematic editorial image with harsh, directional shadows. Maintain the exact scene composition, original white balance, and ensure the overall exposure remains balanced — shadows should be dramatic but the image should not appear underexposed or muddy. Preserve all architectural and interior details. Light source should be the most logical and natural position.",
    "Transform this photo into a cinematic editorial image with harsh, directional shadows. Correct any perspective distortion—ensure vertical lines are truly vertical and horizontal lines are level. Maintain the exact scene composition after correction, preserve original white balance, and ensure the overall exposure remains balanced—shadows should be dramatic but the image should not appear underexposed or muddy. Preserve all architectural and interior details. The scene should feel well-lit yet moody. Derive all lighting direction from visible sources in the frame: windows, doors, architectural openings, and any practical fixtures (lamps, sconces, pendants). Do not introduce light from walls or areas without logical entry points.",
    "Transform this photo into a cinematic editorial image with controlled, directional shadows. Correct any perspective distortion—ensure vertical lines are truly vertical and horizontal lines are level. Maintain the exact scene composition after correction, preserve original white balance, and ensure the overall exposure is bright and airy while retaining depth and dimension. Shadows should add shape and drama without making the space feel dark or dingy. Preserve all architectural and interior details with clarity. The scene should feel inviting, well-lit, and polished. Derive all lighting direction from visible sources in the frame: windows, doors, architectural openings, and any practical fixtures (lamps, sconces, pendants). Do not introduce light from walls or areas without logical entry points",
    "Extreme close-up detail shot of harsh directional light casting crisp shadows across textured interior surface. Tight framing on shadow patterns and light interplay. Cinematic editorial style. Neutral white balance, balanced exposure — deep shadows without underexposure. Sharp texture detail in wood grain, fabric, or architectural elements. Preserve all architectural and interior details.",
    "Extreme close-up detail shot with smooth tracking camera following harsh directional light as it grows and spreads across textured surface. Crisp shadow edges crawl and shift in real time. Camera moves with the light's path revealing texture in wood grain, fabric weave, architectural detail. Editorial film style. Neutral white balance, balanced exposure — deep dramatic shadows without underexposure. Shallow depth of field.",
    "85mm close up detail shot of the main feature in the room. Cinematic editorial style. Neutral white balance, balanced exposure — deep shadows without underexposure. Sharp texture detail in wood grain, fabric, or architectural elements.",
    "85mm close up detail shot of light being cast onto the bathroom cabinets. Cinematic editorial style. Neutral white balance, balanced exposure — deep shadows without underexposure. Sharp texture detail in wood grain, fabric, or architectural elements.",
    "Cinematic detail shot of wood chair with light being cast - maintain white balance - soft bokeh - preserve all architectural and interior details.",
    "Cinematic close up detail shot - maintain white balance - soft bokeh - preserve all architectural and interior details.",
]

images = sorted(glob.glob(str(IMAGES_DIR / "*.jpg")))
print(f"Found {len(images)} images")

clip_files = []

for i, img_path in enumerate(images):
    clip_path = OUTPUT_DIR / f"clip_{i:03d}.mp4"

    if clip_path.exists():
        print(f"[{i+1}/{len(images)}] Skipping {Path(img_path).name} (already done)")
        clip_files.append(str(clip_path))
        continue

    print(f"[{i+1}/{len(images)}] Uploading {Path(img_path).name}...")
    image_url = fal_client.upload_file(img_path)

    print(f"[{i+1}/{len(images)}] Generating clip...")
    try:
        result = fal_client.run(
            "fal-ai/kling-video/v1.6/standard/image-to-video",
            arguments={
                "prompt": PROMPTS[i % len(PROMPTS)],
                "image_url": image_url,
                "duration": "10",
                "aspect_ratio": "16:9",
            }
        )
    except fal_client.client.FalClientHTTPError as e:
        if "content_policy_violation" in str(e):
            print(f"[{i+1}/{len(images)}] SKIPPED: {Path(img_path).name} flagged by content checker")
            continue
        raise

    video_url = result["video"]["url"]
    print(f"[{i+1}/{len(images)}] Downloading clip...")

    import urllib.request
    urllib.request.urlretrieve(video_url, clip_path)
    clip_files.append(str(clip_path))
    print(f"[{i+1}/{len(images)}] Done: {clip_path.name}")

# Combine clips with crossfade transitions
print("Combining clips with crossfade transitions...")
FADE = 1  # seconds of crossfade overlap

# Probe each clip for its actual duration — Kling sometimes returns 5s clips
# even when 10s was requested, so we can't assume a fixed CLIP_DUR.
def probe_duration(path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", path],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    return float(out)

durations = [probe_duration(c) for c in clip_files]
for c, d in zip(clip_files, durations):
    print(f"  {Path(c).name}: {d:.2f}s")

n = len(clip_files)
inputs = []
for clip in clip_files:
    inputs += ["-i", clip]

# Normalize every clip to the same size first — Kling occasionally returns
# clips at different resolutions, which makes xfade fail.
TARGET_W, TARGET_H = 1280, 720

filter_parts = []
for i in range(n):
    filter_parts.append(
        f"[{i}:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=decrease,"
        f"pad={TARGET_W}:{TARGET_H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=30[n{i}]"
    )

# Build xfade chain. Offset for each xfade is the cumulative duration of
# the chain so far minus the fade overlap.
chain_dur = durations[0]
last = "[n0]"
for i in range(1, n):
    offset = chain_dur - FADE
    out = f"[v{i}]" if i < n - 1 else "[vout]"
    filter_parts.append(
        f"{last}[n{i}]xfade=transition=fade:duration={FADE}:offset={offset:.3f}{out}"
    )
    last = f"[v{i}]"
    chain_dur += durations[i] - FADE

filter_str = ";".join(filter_parts)

subprocess.run([
    "ffmpeg", "-y",
    *inputs,
    "-filter_complex", filter_str,
    "-map", "[vout]",
    "-c:v", "libx264", "-crf", "18", "-preset", "fast",
    str(FINAL_VIDEO)
], check=True)

print(f"\nDone! Final video: {FINAL_VIDEO}")
