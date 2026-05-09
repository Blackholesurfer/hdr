# Lensing — Hackathon Plan

> Goal: turn an ordered sequence of real-estate listing photos into a continuous virtual walkthrough video that **also** shows viewpoints not present in the source photos (e.g. back of the house, opposite-side room views).

## Constraints

- Mac (Apple Silicon) — no local CUDA.
- Existing pipeline already on `fal.ai` (Kling v1.6 standard image-to-video).
- Hackathon timeline: ~24–48 hours, demo-driven.
- Bounties targeted: **DeepInvent Top Science Hack** + **Best Use of Miro**.

## Honest framing

You **cannot reconstruct surfaces that were never photographed** — that is a data limit, not a method limit. Reconstruction-only methods (3DGS, NeRF, MASt3R/VGGT) faithfully render the corridor that was walked, then collapse to noise outside it. To show "the back of the house" the only option is **plausible hallucination via a generative prior** (camera-controlled video diffusion).

## The pivot — `Wan 2.2 A14B` likely subsumes `GEN3C` for our hero shot

Original plan was a two-tier split: cinematic camera control via fal.ai (Tier 1) plus a single GEN3C "impossible angle" shot run on Modal/Replicate (Tier 2). Pricing + capability research suggests this is unnecessary:

- `Wan 2.2 A14B` on fal.ai uses **text-prompted** camera motion (pan, dolly, orbit, crane, 360°) with reportedly strong adherence.
- For a single 5–10s hero shot from a clean exterior photo, Wan should be able to produce a 360° orbital "drone" view that hallucinates the back of the house from one input frame.
- That replaces a 2–3hr GEN3C/Modal deployment with one extra fal.ai call.

The key validation step is one test call before committing.

## Pricing reality (fal.ai, 720p, image-to-video)

| Model | $/sec | 10s clip | Camera control |
|---|---|---|---|
| Kling v1.6 standard *(current)* | $0.056 | $0.56 | Implicit / model's discretion |
| **Wan v2.2 A14B** *(proposed)* | $0.08 | $0.80 | **Text-prompted** (adherence reportedly strong) |
| Wan v2.2 A14B Turbo | flat $0.10/video at 720p | $0.10 | Text-prompted |
| Wan v2.2 5B (smaller) | unconfirmed | — | Text-prompted |

Note: the `Wan2.2 Fun Camera Control` variant with explicit per-frame camera path embeddings is **not on fal.ai** — it's on WaveSpeed.ai / self-hosted ComfyUI. Adding a second provider isn't worth it for a hackathon.

## Free win: curate the photo set

Source set is 81 photos, which would yield a ~13-minute output. Real-estate listing videos are 60–90s. Curating to 8–12 hero photos is a free win on cost, length, and demo quality.

| Scope | Kling current | Wan 2.2 reg | Wan 2.2 Turbo (if I2V) |
|---|---|---|---|
| All 81 × 10s | $45.36 | $64.80 | $8.10 |
| **10 hero × 10s** | $5.60 | **$8.00** | $1.00 |

Cost is not a blocker at curated scale.

## Revised plan (8 hours, no GPU, all on fal.ai)

| Phase | Time | What |
|---|---|---|
| 0 | 5m | Curate `images/` to 8–12 hero photos covering: 2 exteriors, 1 entrance, 4–6 hero rooms, 1 backyard, 1 closing exterior. |
| 1 | 30m | **Empirical test** — one Wan 2.2 A14B call on the cleanest front exterior with prompt: *"slow 360° aerial orbit, drone perspective, revealing all four sides of the property and surrounding landscape, cinematic."* Decide: is the back-of-house hallucination demo-quality? |
| 2 | 2–3h | Swap Kling → Wan 2.2 A14B in `pipeline.py`. Update `prompts.json` with per-image camera-direction prompts. |
| 3 | 1–2h | Use Claude Haiku to auto-classify each curated photo and pick a camera move (exterior=pull-back, room=orbit, hallway=dolly). The smart-product layer that differentiates from "we just changed model names." |
| 4 | 1h | The "impossible angle" hero shot is now one prompt in the same pipeline. |
| 5 | 1h | Polish: smooth crossfades (already done), title card, address+agent overlay. |
| 6 | 30m | Pitch + Miro. **DeepInvent**: workflow for sparse real-estate sequences → cinematic walkthrough with hallucinated novel angles. **Miro**: Live Embed of the final video on a board with sticky-note collaboration. |

**Total cost per pipeline run: ~$1–8.** Negligible.

## What to say NO to

- **GEN3C / Modal / Replicate** — only worth deploying if Phase 1's test on Wan 2.2 fails. Don't commit until validated.
- **WaveSpeed.ai's Wan 2.2 Fun Camera (explicit per-frame paths)** — adds a second provider for marginal benefit. Stay on fal.ai.
- **`showcase3d.html` splat viewer for the demo** — keep it in the repo as exploration, but it's a different product. Don't pitch it.
- **Polycam-style local splat scanning** — wrong fit for sparse walkthrough data, doesn't address the "unseen views" goal.
- **Miro Web SDK plugin** — Live Embed satisfies the bounty. A full plugin is an evening of work; ROI vs. DeepInvent prep is bad.
- **Full 81-photo pipeline runs** — wrong product length, wrong cost.

## Risks to monitor

- **Wan 2.2's text-prompted camera adherence may break at extreme angles** (e.g. 360° orbit from a tight-shot exterior). Phase 1 test is exactly to surface this early.
- **Max output duration** for Wan 2.2 A14B on fal.ai is unconfirmed in the listing — Kling did 10s, Wan may cap at 5s. Verify in Phase 1.
- **The "Turbo" variant**'s flat $0.10/video pricing is too good to be true if it's true I2V — confirm with one call before relying on it for cost.

## DeepInvent pitch (the workflow is the invention)

> *A workflow for converting sparse, narrative real-estate photo sequences into continuous virtual walkthrough video including hallucinated novel viewpoints, by combining feed-forward 3D scene caching (MASt3R / GEN3C-style as future work) with camera-trajectory-conditioned video diffusion. Tuned specifically for the underserved real-estate-listing distribution where existing splat/NeRF tools fail (sparse, semi-narrative captures, mix of indoor/outdoor, no controlled capture rig).*

The patent claim is the **specific combination** for the **specific data distribution**, not any single component. Most published novel-view work targets Tanks-and-Temples / MipNeRF360 dense captures — Zillow-style 81-photo walkthroughs are an unaddressed segment.

For the hackathon: ship the camera-controlled diffusion half (Phases 0–4) and pitch the reconstruction-fused half (MASt3R + 3DGS + diffusion fill) as future work. You don't need to have built it to defend the workflow IP.

## Open questions

1. **Test photo for Phase 1**: which exterior in `images/` is cleanest / best-lit / centered for the orbital test?
2. **Curated set**: do you want me to recommend 10 photos for the hero set after viewing them?
3. **GPU fallback access** (Modal / Replicate / vast.ai) — only needed if Phase 1 fails. Free Modal credits are easy to get; Replicate is pay-per-call. Worth lining up in advance.

## References

- [Wan v2.2 A14B Image-to-Video on fal.ai](https://fal.ai/models/fal-ai/wan/v2.2-a14b/image-to-video)
- [Kling v1.6 standard image-to-video on fal.ai](https://fal.ai/models/fal-ai/kling-video/v1.6/standard/image-to-video)
- [Wan v2.2 A14B Turbo](https://fal.ai/models/fal-ai/wan/v2.2-a14b/image-to-video/turbo)
- [Wan 2.2 prompting + camera control guide](https://aikolhub.com/mastering-camera-control-in-wan-2-2-workflow-how-to-guide/)
- [GEN3C — NVIDIA, CVPR 2025 (CUDA reference, future-work fallback)](https://github.com/nv-tlabs/GEN3C)
- [CAT3D — Google, NeurIPS 2024 (closed weights, conceptual reference)](https://proceedings.neurips.cc/paper_files/paper/2024/file/89e4433fec4b99f1d859db57af1e0a0f-Paper-Conference.pdf)
- [Review of Feed-forward 3D Reconstruction (DUSt3R → VGGT)](https://arxiv.org/abs/2507.08448)
- [Sparse-view 3DGS review](https://link.springer.com/article/10.1007/s10462-025-11171-4)
