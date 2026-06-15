"""
vision_service.py — provider-routed grading (Bedrock Nova | Gemini | stub).

assess_media() takes the case's media (images and/or a video) for a stage and
returns an AIAssessmentCreate, so the result flows through the existing
viability -> routing -> health-card -> listing pipeline unchanged.

VISION_PROVIDER (default "bedrock"):
  bedrock -> Amazon Bedrock Nova Lite (image + video). AWS-native.
  gemini  -> Google Gemini (image inline + video via File API).
  stub    -> low-confidence placeholder -> routes to MANUAL_REVIEW.
Provider failures cascade to the next configured AI provider; stub/manual review is used only if all AI providers fail.
"""
from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import time
from typing import Optional

from app.config import get_settings
from app.constants import InspectionStage, PackagingCondition, UsageLevel
from app.models import ReturnCase
from app.schemas import AIAssessmentCreate

log = logging.getLogger("vision_service")

GRADE_HEALTH_FALLBACK = {"A": 92, "B": 78, "C": 58, "D": 28}

_PROMPT = """You are an expert e-commerce returns inspector. Examine the product image(s) or video and assess the item's physical condition for resale.
Grades: A = like-new/unused; B = light use, minor marks; C = noticeable wear or missing packaging/accessories; D = damaged/unsellable.
Return product_health_score as an integer from 1 to 100 using these anchors: A=85-100, B=70-84, C=45-69, D=1-44. Never return 0 for a visible product.
Judge only what is visible; if ambiguous, grade lower and lower confidence. If given a video, inspect the whole clip.
Respond with ONLY this JSON object:
{"grade":"A","product_health_score":92,"visible_damage":"short description","packaging_condition":"SEALED|GOOD|WORN|DAMAGED|MISSING","usage_level":"UNUSED|LIGHT|MODERATE|HEAVY|UNKNOWN","missing_parts":false,"confidence":0.0,"buyer_facing_summary":"one concise line for buyers"}"""


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


def _coerce(data: dict, stage: InspectionStage) -> AIAssessmentCreate:
    grade = str(data.get("grade", "C")).strip().upper()[:1]
    grade = grade if grade in {"A", "B", "C", "D"} else "C"
    try:
        health = int(round(float(data.get("product_health_score"))))
    except (TypeError, ValueError):
        health = -1
    if not (1 <= health <= 100):
        # Vision models sometimes echo the JSON example placeholder (0) instead of scoring.
        # Keep routing deterministic by anchoring score to the validated grade.
        health = GRADE_HEALTH_FALLBACK[grade]
    pack = str(data.get("packaging_condition", "GOOD")).strip().upper()
    pack = pack if pack in {e.value for e in PackagingCondition} else "GOOD"
    usage = str(data.get("usage_level", "UNKNOWN")).strip().upper()
    usage = usage if usage in {e.value for e in UsageLevel} else "UNKNOWN"
    try:
        conf = max(0.0, min(1.0, float(data.get("confidence", 0.5))))
    except (TypeError, ValueError):
        conf = 0.5
    return AIAssessmentCreate(
        stage=stage,
        grade=grade,
        product_health_score=health,
        visible_damage=str(data.get("visible_damage", "Not specified"))[:500],
        packaging_condition=pack,
        usage_level=usage,
        missing_parts=bool(data.get("missing_parts", False)),
        confidence=conf,
        buyer_facing_summary=str(data.get("buyer_facing_summary", "Inspected returned item."))[:500],
    )


def _prompt_for(return_case: ReturnCase) -> str:
    return (_PROMPT + f"\nProduct: {return_case.product_name} | Category: {return_case.category}"
            f" | Return reason: {return_case.return_reason}")


def _grade_bedrock(prompt, images, video, stage):
    import boto3
    settings = get_settings()
    client = boto3.client("bedrock-runtime", region_name=settings.aws_region)
    content: list = [{"text": prompt}]
    for data, ctype in images:
        fmt = (ctype.split("/")[-1] or "jpeg").lower()
        fmt = "jpeg" if fmt == "jpg" else fmt
        content.append({"image": {"format": fmt, "source": {"bytes": data}}})
    if video is not None:
        data, ctype, _name = video
        fmt = (ctype.split("/")[-1] or "mp4").lower()
        content.append({"video": {"format": fmt, "source": {"bytes": data}}})
    resp = client.converse(
        modelId=settings.bedrock_model_id,
        messages=[{"role": "user", "content": content}],
        inferenceConfig={"temperature": 0, "maxTokens": 600},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    return _coerce(_extract_json(text), stage)


def _grade_gemini(prompt, images, video, stage):
    from google import genai
    from google.genai import types
    settings = get_settings()
    client = genai.Client(api_key=settings.gemini_api_key)
    parts: list = [prompt]
    if video is not None:
        data, _ctype, name = video
        suffix = os.path.splitext(name)[1] or ".mp4"
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        tmp.write(data); tmp.flush(); tmp.close()

        def _state(f):
            st = getattr(f, "state", None)
            return getattr(st, "name", str(st)).upper()
        vid = client.files.upload(file=tmp.name)
        waited = 0
        while _state(vid) == "PROCESSING" and waited < 180:
            time.sleep(2); waited += 2; vid = client.files.get(name=vid.name)
        if _state(vid) != "ACTIVE":
            raise RuntimeError(f"video not ready ({_state(vid)})")
        parts.append(vid)
    else:
        for data, ctype in images:
            parts.append(types.Part.from_bytes(data=data, mime_type=ctype))
    resp = client.models.generate_content(
        model=settings.gemini_model, contents=parts,
        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0))
    return _coerce(_extract_json(resp.text), stage)


def _stub(stage):
    return _coerce({
        "grade": "B", "product_health_score": 70,
        "visible_damage": "No automated grader available; manual inspection required.",
        "packaging_condition": "GOOD", "usage_level": "UNKNOWN", "missing_parts": False,
        "confidence": 0.5, "buyer_facing_summary": "Pending verified inspection.",
    }, stage)


def assess_media(
    return_case: ReturnCase,
    stage: InspectionStage,
    images: list[tuple[bytes, str]],
    video: Optional[tuple[bytes, str, str]],
) -> AIAssessmentCreate:
    if not images and video is None:
        return _stub(stage)

    settings = get_settings()
    primary_provider = (settings.vision_provider or "bedrock").lower().strip()
    prompt = _prompt_for(return_case)

    # Preferred production path:
    # 1. Try the configured primary provider.
    # 2. If Bedrock is throttled/unavailable, try Gemini 2.5 Flash.
    # 3. Use stub/manual-review only if every AI provider fails.
    if primary_provider == "bedrock":
        providers = ["bedrock", "gemini", "stub"]
    elif primary_provider == "gemini":
        providers = ["gemini", "bedrock", "stub"]
    elif primary_provider == "stub":
        providers = ["stub"]
    else:
        providers = ["bedrock", "gemini", "stub"]

    last_error = None

    for provider in providers:
        if provider == "stub":
            break

        if provider == "gemini" and not settings.gemini_api_key:
            log.warning("vision grading via gemini skipped (GEMINI_API_KEY missing)")
            continue

        try:
            if provider == "bedrock":
                return _grade_bedrock(prompt, images, video, stage)

            if provider == "gemini":
                return _grade_gemini(prompt, images, video, stage)

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            log.warning(
                "vision grading via %s failed (%s) -> trying next provider",
                provider,
                exc,
            )

    log.warning("all vision providers failed (%s) -> stub", last_error)
    return _stub(stage)
