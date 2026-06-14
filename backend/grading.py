"""
grading.py — the AI seam (multi-provider: Gemini | Ollama | stub)
-----------------------------------------------------------------
`grade_item()` keeps its contract (returns GradeResult). It now routes to a
provider chosen by the GRADER_PROVIDER env var (default "auto"):

  gemini  -> Google Gemini API. Handles IMAGES *and* VIDEO. Free tier, no GPU.
  ollama  -> local Qwen2.5-VL. Images only (Ollama can't take video). Offline.
  stub    -> deterministic fallback (no model needed).
  auto    -> gemini if GEMINI_API_KEY is set, else ollama if available, else stub.

Video is supported ONLY on gemini (Ollama has no video input). Pass video_path.

Setup for Gemini:
    pip install google-genai
    export GEMINI_API_KEY=...        # free key from https://aistudio.google.com
    export GEMINI_MODEL=gemini-2.5-flash   # or gemini-3-flash; must be a vision model
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import tempfile
import time
from pathlib import Path
from typing import Optional

from models import Grade, GradeResult

log = logging.getLogger("grading")

PROVIDER = os.getenv("GRADER_PROVIDER", "auto").lower()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
OLLAMA_MODEL = os.getenv("QWEN_MODEL", "qwen2.5vl:7b")
MAX_IMAGE_PX = int(os.getenv("GRADE_MAX_IMAGE_PX", "768"))
CONFIDENCE_REVIEW_THRESHOLD = 0.55

# The inspector's manual — the grading knowledge. Tune THIS, not the model.
_PROMPT = """You are an expert returns-inspection assistant for an e-commerce platform.
Examine the product image(s) or video and assess the item's PHYSICAL CONDITION for resale.

Grade rubric:
- A: Like new / unused. No visible wear; packaging and accessories appear intact.
- B: Light use. Minor cosmetic marks only; fully functional; cheaply refurbished.
- C: Noticeable wear, or missing packaging/accessories. Usable but below resale-new.
- D: Damaged, broken, or unsellable.

Rules:
- Judge ONLY what is visible. Do not invent hidden defects, but be conservative:
  if condition is ambiguous, grade lower AND lower your confidence.
- If given a video, inspect the item across the whole clip (all angles/frames).
- findings = short concrete observations. 1-4 items.
- Respond with ONLY this JSON object, nothing else:
{"grade":"A","condition_score":0,"findings":["..."],"confidence":0.0}
"""

_MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png",
         ".webp": "image/webp", ".mp4": "video/mp4", ".mov": "video/quicktime",
         ".webm": "video/webm"}


# --------------------------------------------------------------------------- #
# Stub fallback
# --------------------------------------------------------------------------- #
_GRADE_PROFILE = {
    Grade.A: (92, ["Unused / sealed", "No visible wear", "All accessories present"]),
    Grade.B: (74, ["Light cosmetic wear", "Fully functional", "Minor scuff noted"]),
    Grade.C: (48, ["Visible wear", "Works but not resell-grade", "Packaging missing"]),
    Grade.D: (15, ["Damage detected", "Not functional", "Recommend recycle"]),
}


def _stub_grade(seed_parts: list[str]) -> Grade:
    h = int(hashlib.sha256("|".join(seed_parts).encode()).hexdigest(), 16)
    return [Grade.A, Grade.B, Grade.C, Grade.D][h % 4]


def _stub_result(seed_parts: list[str], grade: Optional[Grade] = None) -> GradeResult:
    grade = grade or _stub_grade(seed_parts)
    score, findings = _GRADE_PROFILE[grade]
    return GradeResult(grade=grade, condition_score=score, findings=findings, confidence=0.80)


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #
def _mime(path: str) -> str:
    return _MIME.get(Path(path).suffix.lower(), "application/octet-stream")


def _downscale(path: str) -> str:
    try:
        from PIL import Image
        img = Image.open(path)
        if max(img.size) <= MAX_IMAGE_PX:
            return path
        img.thumbnail((MAX_IMAGE_PX, MAX_IMAGE_PX))
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        img.convert("RGB").save(tmp.name, quality=85)
        return tmp.name
    except Exception:
        return path


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass
    text = re.sub(r"```(?:json)?", "", text)
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        raise ValueError(f"no JSON in model output: {text[:200]!r}")
    return json.loads(m.group(0))


def _to_result(data: dict) -> GradeResult:
    raw = str(data.get("grade", "C")).strip().upper()[:1]
    grade = Grade(raw) if raw in {"A", "B", "C", "D"} else Grade.C
    try:
        score = max(0, min(100, int(round(float(data.get("condition_score", 50))))))
    except (TypeError, ValueError):
        score = 50
    findings = data.get("findings", [])
    findings = [findings] if isinstance(findings, str) else findings
    findings = [str(f) for f in findings][:4] or ["No findings reported"]
    try:
        conf = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    return GradeResult(grade=grade, condition_score=score, findings=findings, confidence=conf)


# --------------------------------------------------------------------------- #
# Provider: Gemini  (images + video)
# --------------------------------------------------------------------------- #
def _grade_gemini(image_paths: list[str], category: str,
                  video_path: Optional[str]) -> GradeResult:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    parts: list = [_PROMPT + f"\nProduct category: {category}."]

    if video_path:                                  # upload + wait until ACTIVE
        def _state(f) -> str:
            st = getattr(f, "state", None)
            return getattr(st, "name", str(st)).upper()

        vid = client.files.upload(file=video_path)
        waited = 0
        while _state(vid) == "PROCESSING" and waited < 180:
            time.sleep(2)
            waited += 2
            vid = client.files.get(name=vid.name)
        if _state(vid) != "ACTIVE":
            raise RuntimeError(
                f"video not ready (state={_state(vid)}) after {waited}s")
        parts.append(vid)
    else:
        for p in image_paths:
            sp = _downscale(p)
            parts.append(types.Part.from_bytes(data=Path(sp).read_bytes(),
                                                mime_type=_mime(p)))

    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json",
                                            temperature=0),
    )
    return _to_result(_extract_json(resp.text))


# --------------------------------------------------------------------------- #
# Provider: Ollama / Qwen2.5-VL  (images only)
# --------------------------------------------------------------------------- #
def _grade_ollama(image_paths: list[str], category: str) -> GradeResult:
    import ollama
    images = [_downscale(p) for p in image_paths]
    resp = ollama.chat(
        model=OLLAMA_MODEL,
        format="json",
        messages=[{"role": "user",
                   "content": _PROMPT + f"\nProduct category: {category}.",
                   "images": images}],
        options={"temperature": 0, "num_predict": 256},
        keep_alive="-1",                            # stay warm: no cold start after 1st
    )
    return _to_result(_extract_json(resp["message"]["content"]))


# --------------------------------------------------------------------------- #
# Provider selection
# --------------------------------------------------------------------------- #
def _resolve_provider(video: bool) -> str:
    if PROVIDER != "auto":
        return PROVIDER
    if os.getenv("GEMINI_API_KEY"):
        return "gemini"
    if video:
        return "stub"                               # ollama can't do video
    try:
        import ollama  # noqa: F401
        return "ollama"
    except Exception:
        return "stub"


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def grade_item(
    image_paths: list[str],
    category: str,
    mock_grade: Optional[Grade] = None,
    video_path: Optional[str] = None,
) -> GradeResult:
    """Assess condition from image(s) OR a video. Returns a GradeResult.
    Video is only graded by the gemini provider (Ollama has no video input)."""
    seed = (image_paths or []) + ([video_path] if video_path else []) + [category]

    if mock_grade is not None:
        return _stub_result(seed, mock_grade)
    if not image_paths and not video_path:
        return _stub_result(seed, Grade.C).model_copy(
            update={"confidence": 0.3, "findings": ["No media provided"]})

    provider = _resolve_provider(video=bool(video_path))
    try:
        if provider == "gemini":
            return _grade_gemini(image_paths, category, video_path)
        if provider == "ollama":
            if video_path:
                raise RuntimeError("ollama cannot grade video; set GEMINI_API_KEY")
            return _grade_ollama(image_paths, category)
        return _stub_result(seed)
    except Exception as e:
        log.warning("grading via %s failed (%s) -> stub", provider, e)
        return _stub_result(seed)


def needs_review(result: GradeResult) -> bool:
    """Too uncertain to auto-list -> route to human review."""
    return result.confidence < CONFIDENCE_REVIEW_THRESHOLD
