import json
import base64
import re
import time

import httpx

from config.settings import settings
from services.web_search_service import web_search


class GroqServiceError(RuntimeError):
    pass


_SYMPTOM_CACHE: dict[str, tuple[float, dict]] = {}
_UNCERTAINTY_CACHE: dict[str, tuple[float, dict]] = {}
_CHAT_PROMPT_VERSION = "v5"
_SYMPTOM_PROMPT_VERSION = "v2"


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _default_symptom_output(symptoms: str) -> dict:
    text = symptoms.lower()
    disease = "non-specific condition"
    severity = "moderate"
    risk = "medium"
    probability = 0.45

    if "bleeding" in text or "unconscious" in text:
        disease = "possible acute emergency"
        severity = "critical"
        risk = "high"
        probability = 0.8
    elif "pain" in text and "bone" in text:
        disease = "possible fracture"
        severity = "high"
        risk = "high"
        probability = 0.7
    elif "lump" in text or "mass" in text:
        disease = "possible tumor"
        severity = "high"
        risk = "high"
        probability = 0.68
    elif "flank" in text or "urine" in text:
        disease = "possible kidney stone"
        severity = "moderate"
        risk = "medium"
        probability = 0.62
    elif (("abdominal" in text or "abdomen" in text or "stomach" in text or "cramp" in text) and ("vomit" in text or "vomiting" in text or "nausea" in text)):
        disease = "acute_gastrointestinal_syndrome_suspected"
        severity = "high"
        risk = "high"
        probability = 0.74
    elif "cough" in text or "throat" in text or "sore throat" in text:
        disease = "upper_respiratory_tract_infection_suspected"
        severity = "moderate"
        risk = "medium"
        probability = 0.64

    return {
        "disease": disease,
        "probability": probability,
        "severity": severity,
        "risk": risk,
        "missing_inputs": [],
        "follow_up_questions": [
            "What is the patient symptom timeline and progression?",
            "Any red flags or objective findings that change risk stratification?",
        ],
        "clinical_reasoning": "Rule-based fallback reasoning was applied from symptom keywords.",
        "summary": "Generated using rule-based fallback because Groq API is unavailable.",
        "source": "fallback",
    }


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GroqServiceError("Groq response does not contain valid JSON")
    snippet = text[start : end + 1]
    return json.loads(snippet)


def _normalize_symptoms(symptoms: str) -> str:
    return " ".join((symptoms or "").strip().lower().split())


def _cache_get(key: str) -> dict | None:
    ttl = max(1, settings.groq_cache_ttl_seconds)
    cached = _SYMPTOM_CACHE.get(key)
    if cached is None:
        return None

    created_at, payload = cached
    if (time.time() - created_at) > ttl:
        _SYMPTOM_CACHE.pop(key, None)
        return None
    return payload


def _cache_set(key: str, payload: dict) -> None:
    _SYMPTOM_CACHE[key] = (time.time(), payload)


def _uncertainty_cache_get(key: str) -> dict | None:
    ttl = max(1, settings.groq_cache_ttl_seconds)
    cached = _UNCERTAINTY_CACHE.get(key)
    if cached is None:
        return None

    created_at, payload = cached
    if (time.time() - created_at) > ttl:
        _UNCERTAINTY_CACHE.pop(key, None)
        return None
    return payload


def _uncertainty_cache_set(key: str, payload: dict) -> None:
    _UNCERTAINTY_CACHE[key] = (time.time(), payload)


def _normalize_structured_output(parsed: dict) -> dict:
    return {
        "disease": str(parsed.get("disease", "non-specific condition")),
        "probability": max(0.0, min(1.0, _safe_float(parsed.get("probability"), 0.45))),
        "severity": str(parsed.get("severity", "moderate")).lower(),
        "risk": str(parsed.get("risk", "medium")).lower(),
        "missing_inputs": parsed.get("missing_inputs", []) or [],
        "follow_up_questions": parsed.get("follow_up_questions", []) or [],
        "clinical_reasoning": str(parsed.get("clinical_reasoning", "")),
        "summary": str(parsed.get("summary", "")),
        "source": str(parsed.get("source", "groq")).lower(),
    }


def _image_to_data_url(image_bytes: bytes) -> str:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{encoded}"


async def analyze_image_with_groq(image_bytes: bytes, symptoms: str | None, image_context: dict | None = None) -> dict:
    fallback_output = {
        "disease": "skin condition",
        "probability": 0.55,
        "severity": "moderate",
        "risk": "medium",
        "follow_up_questions": [
            "Provide patient symptom duration and progression correlated with image findings.",
            "Document associated red flags (fever, bleeding, severe pain, rapid progression).",
        ],
        "clinical_reasoning": "Fallback used because Groq image analysis was unavailable.",
        "summary": "Image triage used fallback output.",
        "source": "fallback",
    }

    api_key = settings.groq_api_key
    if not api_key:
        return fallback_output

    data_url = _image_to_data_url(image_bytes)
    context_text = json.dumps(image_context or {}, default=str)

    prompt = (
        "You are Pulse, a medical triage assistant for physician users. Analyze the provided medical image and optional symptoms. "
        "Return ONLY valid JSON using this schema: "
        "{"
        "\"disease\": string,"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"follow_up_questions\": string[] (max 4, phrased for clinicians),"
        "\"clinical_reasoning\": string (max 70 words),"
        "\"summary\": string (max 30 words),"
        "\"source\": \"groq_vision\""
        "}."
        f"\nSymptoms/clinical context: {symptoms or 'not provided'}"
        f"\nImage context: {context_text}"
    )

    payload = {
        "model": settings.groq_vision_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You produce concise medical triage JSON from images and symptoms."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        timeout = httpx.Timeout(25.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        return {
            "disease": str(parsed.get("disease", fallback_output["disease"])),
            "probability": max(0.0, min(1.0, _safe_float(parsed.get("probability"), fallback_output["probability"]))),
            "severity": str(parsed.get("severity", fallback_output["severity"])).lower(),
            "risk": str(parsed.get("risk", fallback_output["risk"])).lower(),
            "follow_up_questions": parsed.get("follow_up_questions", []) or fallback_output["follow_up_questions"],
            "clinical_reasoning": str(parsed.get("clinical_reasoning", fallback_output["clinical_reasoning"])),
            "summary": str(parsed.get("summary", fallback_output["summary"])),
            "source": str(parsed.get("source", "groq_vision")).lower(),
        }
    except Exception:
        return fallback_output


async def generate_recommendations_with_groq(image_bytes: bytes, condition: str, symptoms: str | None) -> dict:
    api_key = settings.groq_api_key
    if not api_key:
        raise GroqServiceError("Groq API key missing")

    data_url = _image_to_data_url(image_bytes)
    prompt = (
        "You are Pulse, a medical support assistant. Based on the image, suspected condition, and symptoms, "
        "return ONLY valid JSON with this schema: "
        "{"
        "\"disease_key\": string,"
        "\"drugs\": string[],"
        "\"procedures\": string[],"
        "\"tests\": string[],"
        "\"doctor_note\": string (max 80 words, experienced and reassuring clinical tone),"
        "\"source\": \"groq_vision\""
        "}. "
        "Keep recommendations concise and conservative (supportive care + specialist guidance). "
        "The doctor_note must sound like an experienced senior clinician: clear, calm, practical, and safety-focused."
        f"\nCondition: {condition or 'unknown'}"
        f"\nSymptoms: {symptoms or 'not provided'}"
    )

    payload = {
        "model": settings.groq_vision_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You output concise recommendation JSON only."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async def _request_and_parse(request_payload: dict) -> dict:
        timeout = httpx.Timeout(25.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=request_payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _extract_json(content)

    try:
        parsed = await _request_and_parse(payload)
    except Exception:
        text_only_payload = {
            "model": settings.groq_model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You output concise recommendation JSON only."},
                {
                    "role": "user",
                    "content": (
                        "Generate recommendations for suspected medical condition. "
                        "Return ONLY JSON schema: {\"disease_key\":string,\"drugs\":string[],\"procedures\":string[],\"tests\":string[],\"doctor_note\":string,\"source\":\"groq\"}. "
                        "Keep it conservative and concise. "
                        "Write doctor_note in a seasoned senior-clinician tone. "
                        f"Condition: {condition or 'unknown'}. Symptoms: {symptoms or 'not provided'}."
                    ),
                },
            ],
        }
        parsed = await _request_and_parse(text_only_payload)

    def _as_list(value):
        if not isinstance(value, list):
            return []
        return [str(item) for item in value if str(item).strip()]

    return {
        "disease_key": str(parsed.get("disease_key", (condition or "general_non_specific_finding"))).strip().lower().replace(" ", "_"),
        "drugs": _as_list(parsed.get("drugs")),
        "procedures": _as_list(parsed.get("procedures")),
        "tests": _as_list(parsed.get("tests")),
        "doctor_note": str(parsed.get("doctor_note", "")).strip(),
        "source": str(parsed.get("source", "groq_vision")),
    }


async def generate_text_recommendations_with_groq(condition: str, symptoms: str | None, risk_level: str | None = None) -> dict:
    api_key = settings.groq_api_key
    if not api_key:
        raise GroqServiceError("Groq API key missing")

    web_context = await web_search(f"clinical triage recommendations and supportive care for: {symptoms or condition}")
    web_context_text = web_context or "No external web snippet available. Use conservative, guideline-style clinical reasoning."

    prompt = (
        "You are Pulse, a physician-facing clinical assistant. "
        "Return ONLY valid JSON using this exact schema: "
        "{"
        "\"disease_key\": string,"
        "\"primary_drug\": string,"
        "\"drugs\": string[] (include at least one conservative symptomatic first-line option unless contraindicated),"
        "\"alternative_drugs\": string[],"
        "\"safety_cautions\": string[],"
        "\"procedures\": string[],"
        "\"tests\": string[],"
        "\"doctor_note\": string (max 90 words, practical and safety-focused),"
        "\"source\": \"groq\""
        "}. "
        "The most apt drug must be in primary_drug and also be the first item in drugs. "
        "Keep recommendations conservative, avoid high-risk medications without context, and include red-flag escalation advice in safety_cautions. "
        f"Condition hint: {condition or 'general_non_specific_finding'}. "
        f"Risk level: {risk_level or 'medium'}. "
        f"Symptoms: {symptoms or 'not provided'}. "
        f"Web context: {web_context_text}"
    )

    payload = {
        "model": settings.groq_model,
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You produce concise physician-facing recommendation JSON only."},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    async def _request_and_parse(request_payload: dict) -> dict:
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=request_payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        return _extract_json(content)

    try:
        parsed = await _request_and_parse(payload)
    except Exception:
        retry_payload = {
            "model": settings.groq_model,
            "temperature": 0.1,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": "Return JSON only. No prose. Schema keys required: disease_key, primary_drug, drugs, alternative_drugs, safety_cautions, procedures, tests, doctor_note, source.",
                },
                {
                    "role": "user",
                    "content": (
                        "Return strict JSON only for physician-facing supportive recommendations. "
                        f"Condition: {condition or 'general_non_specific_finding'}. "
                        f"Risk: {risk_level or 'medium'}. "
                        f"Symptoms: {symptoms or 'not provided'}. "
                        f"Web: {web_context_text}"
                    ),
                },
            ],
        }
        parsed = await _request_and_parse(retry_payload)

    def _as_list(value):
        if not isinstance(value, list):
            return []
        return [str(item).strip() for item in value if str(item).strip()]

    def _default_drugs_for_text(symptom_or_condition: str) -> list[str]:
        combined = str(symptom_or_condition or "").lower()
        gi_markers = {"abdominal", "abdomen", "stomach", "cramp", "cramps", "vomit", "vomiting", "nausea", "diarrhea"}
        pain_markers = {"pain", "hip", "back", "spine", "lumbar", "muscle", "joint", "sciatica"}
        respiratory_markers = {"cough", "throat", "cold", "sore throat"}
        gastric_markers = {"acidity", "gastric", "reflux", "heartburn"}

        if any(marker in combined for marker in gi_markers):
            return ["ondansetron (if no contraindications)", "pantoprazole", "paracetamol"]
        if any(marker in combined for marker in pain_markers):
            return ["ibuprofen (if no contraindications)", "paracetamol"]
        if any(marker in combined for marker in respiratory_markers):
            return ["cetirizine", "paracetamol"]
        if any(marker in combined for marker in gastric_markers):
            return ["pantoprazole", "antacid"]
        return ["ibuprofen (if no contraindications)", "paracetamol"]

    primary_drug = str(parsed.get("primary_drug", "")).strip()
    drugs = _as_list(parsed.get("drugs"))
    if primary_drug:
        drugs = [primary_drug, *[item for item in drugs if item.lower() != primary_drug.lower()]]
    if not drugs:
        drugs = _default_drugs_for_text(f"{condition or ''} {symptoms or ''}")

    return {
        "disease_key": str(parsed.get("disease_key", (condition or "general_non_specific_finding"))).strip().lower().replace(" ", "_"),
        "primary_drug": primary_drug or drugs[0],
        "drugs": drugs,
        "alternative_drugs": _as_list(parsed.get("alternative_drugs")),
        "safety_cautions": _as_list(parsed.get("safety_cautions")),
        "procedures": _as_list(parsed.get("procedures")),
        "tests": _as_list(parsed.get("tests")),
        "doctor_note": str(parsed.get("doctor_note", "")).strip(),
        "source": str(parsed.get("source", "groq")).strip() or "groq",
    }


async def analyze_symptoms_with_groq(symptoms: str) -> dict:
    normalized_symptoms = _normalize_symptoms(symptoms)
    if not normalized_symptoms:
        return {
            "disease": "insufficient symptom data",
            "probability": 0.0,
            "severity": "low",
            "risk": "low",
            "missing_inputs": ["symptoms"],
            "follow_up_questions": ["Provide key patient symptoms with onset, duration, and progression."],
            "clinical_reasoning": "No symptom content was supplied.",
            "summary": "Symptom analysis skipped due to empty input.",
            "source": "empty-input",
        }

    cache_key = f"symptom::{_SYMPTOM_PROMPT_VERSION}::{normalized_symptoms}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return {**cached, "source": "cache"}

    api_key = settings.groq_api_key
    if not api_key:
        fallback = _default_symptom_output(symptoms)
        _cache_set(cache_key, fallback)
        return fallback

    web_context = await web_search(f"medical differential and triage guidance for: {symptoms}")
    web_context_text = web_context or "No web snippets available; use conservative clinical triage reasoning."

    prompt = (
        "You are Pulse, a medical triage assistant for physician users. Given symptoms, return ONLY valid JSON and no markdown. "
        "Do NOT provide medications, drugs, dosages, procedures, or test recommendations. "
        "Only provide diagnostic triage fields defined below. "
        "Use this exact schema: "
        "{"
        "\"disease\": string,"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"missing_inputs\": string[],"
        "\"follow_up_questions\": string[] (max 4 concise clinician-facing questions),"
        "\"clinical_reasoning\": string (max 70 words),"
        "\"summary\": string (max 30 words),"
        "\"source\": \"groq\""
        "}."
        "\nWeb context (latest snippets; prioritize higher-confidence consensus and note uncertainty when conflicting): "
        f"{web_context_text}"
        "\nSymptoms: "
        f"{symptoms}"
    )

    payload = {
        "model": settings.groq_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are Pulse, a concise clinical triage assistant that produces JSON."},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)
        structured = _normalize_structured_output(parsed)
        if web_context and structured.get("source") == "groq":
            structured["source"] = "groq_web"
        _cache_set(cache_key, structured)
        return structured
    except Exception as exc:
        fallback = _default_symptom_output(symptoms)
        fallback["summary"] = f"Groq unavailable, fallback used: {exc}"
        if web_context:
            fallback["clinical_reasoning"] = (
                f"Rule-based fallback with web context support. Snippets: {web_context_text[:300]}"
            )
        _cache_set(cache_key, fallback)
        return fallback


async def analyze_uncertain_image_with_groq(symptoms: str | None, image_context: dict) -> dict:
    normalized_symptoms = _normalize_symptoms(symptoms or "")
    context_key = json.dumps(image_context, sort_keys=True, default=str)
    cache_key = f"{normalized_symptoms}::{context_key}"
    cached = _uncertainty_cache_get(cache_key)
    if cached is not None:
        return {**cached, "source": "cache"}

    fallback_output = {
        "disease": "general non-specific finding",
        "probability": 0.35,
        "severity": "moderate",
        "risk": "medium",
        "uncertainty": 0.75,
        "follow_up_questions": [
            "Provide a higher-quality image from an alternate angle/modality for clinical correlation.",
            "List key associated symptoms, duration, and objective exam findings.",
        ],
        "clinical_reasoning": "Image confidence/routing was insufficient; produced conservative general analysis.",
        "summary": "General analysis due to uncertain image interpretation.",
        "source": "fallback",
    }

    api_key = settings.groq_api_key
    if not api_key:
        _uncertainty_cache_set(cache_key, fallback_output)
        return fallback_output

    prompt = (
        "You are Pulse, a medical triage assistant for physician users. An image analysis is uncertain. "
        "Do NOT provide medications, drugs, dosages, procedures, or test recommendations. "
        "Only provide uncertainty-aware diagnostic triage fields defined below. "
        "Return ONLY valid JSON with exact schema: "
        "{"
        "\"disease\": string,"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"uncertainty\": number(0-1),"
        "\"follow_up_questions\": string[] (max 4, clinician-facing),"
        "\"clinical_reasoning\": string (max 70 words),"
        "\"summary\": string (max 30 words),"
        "\"source\": \"groq\""
        "}."
        "\nKnown context:\n"
        f"- Symptoms: {symptoms or 'not provided'}\n"
        f"- Image context: {context_key}\n"
        "If uncertain, keep probability <= 0.5 and uncertainty >= 0.5."
    )

    payload = {
        "model": settings.groq_model,
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You produce concise uncertainty-aware triage JSON."},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = _extract_json(content)

        structured = {
            "disease": str(parsed.get("disease", fallback_output["disease"])),
            "probability": max(0.0, min(1.0, _safe_float(parsed.get("probability"), fallback_output["probability"]))),
            "severity": str(parsed.get("severity", fallback_output["severity"])).lower(),
            "risk": str(parsed.get("risk", fallback_output["risk"])).lower(),
            "uncertainty": max(0.0, min(1.0, _safe_float(parsed.get("uncertainty"), fallback_output["uncertainty"]))),
            "follow_up_questions": parsed.get("follow_up_questions", []) or fallback_output["follow_up_questions"],
            "clinical_reasoning": str(parsed.get("clinical_reasoning", fallback_output["clinical_reasoning"])),
            "summary": str(parsed.get("summary", fallback_output["summary"])),
            "source": str(parsed.get("source", "groq")).lower(),
        }
        _uncertainty_cache_set(cache_key, structured)
        return structured
    except Exception as exc:
        fallback = {**fallback_output, "summary": f"Groq unavailable, fallback used: {exc}"}
        _uncertainty_cache_set(cache_key, fallback)
        return fallback


_CHAT_CACHE: dict[str, tuple[float, str]] = {}


def _chat_cache_get(key: str) -> str | None:
    ttl = max(1, settings.groq_cache_ttl_seconds)
    cached = _CHAT_CACHE.get(key)
    if cached is None:
        return None
    created_at, payload = cached
    if (time.time() - created_at) > ttl:
        _CHAT_CACHE.pop(key, None)
        return None
    return payload


def _chat_cache_set(key: str, payload: str) -> None:
    _CHAT_CACHE[key] = (time.time(), payload)


def _sanitize_physician_chat_response(text: str, include_access_policy: bool = True) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"(?i)this\s+system\s+is\s+for\s+verified\s+physicians\s+and\s+clinicians\s+only[^.?!]*[.?!]?", "", cleaned)
    cleaned = re.sub(r"(?i)\bconsult\s+(with\s+)?your\s+(own\s+)?physician\b[^.?!]*[.?!]?", "", cleaned)
    cleaned = re.sub(r"(?i)\bthis\s+does\s+not\s+replace\s+medical\s+advice\b[^.?!]*[.?!]?", "", cleaned)
    cleaned = re.sub(r"(?i)\balways\s+important\s+to\s+consult\s+your\s+physician\b[^.?!]*[.?!]?", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    layperson_markers = [
        "how can i assist you today",
        "i'm here to listen",
        "general advice on maintaining your health",
        "your healthcare routine",
        "your unique needs",
        "what's on your mind today",
        "if you're not sure where to start",
        "how have you been feeling",
        "i hope you're doing well",
        "your recovery",
        "daily activities",
    ]

    lowered = cleaned.lower()
    has_layperson_tone = any(marker in lowered for marker in layperson_markers)

    if has_layperson_tone:
        cleaned = (
            "Hey colleague! Happy to help with whatever you're working on. "
            "Share the clinical scenario — symptoms, imaging, differentials — and I'll keep it practical and actionable."
        )

    # Allow up to 5 sentences for adequate answers, trim only if excessively long.
    sentence_chunks = re.split(r"(?<=[.!?])\s+", cleaned)
    if len(sentence_chunks) > 6:
        cleaned = " ".join(chunk.strip() for chunk in sentence_chunks[:5] if chunk.strip())

    if include_access_policy:
        access_line = "Access policy: this assistant is intended for verified physicians/clinicians only; non-verified users must not use it."
        if access_line.lower() not in cleaned.lower():
            cleaned = f"{access_line}\n\n{cleaned}" if cleaned else access_line
    return cleaned


async def chat_followup_with_groq(user_message: str, conversation_context: str = "") -> str:
    """Generate a conversational paragraph response for follow-up questions (no structured template).

    For general knowledge questions the function performs a quick web search and feeds the
    results into the LLM prompt so it can give grounded, up-to-date answers.
    """
    normalized = _normalize_symptoms(user_message)
    cache_key = f"chat::{_CHAT_PROMPT_VERSION}::{normalized}::{_normalize_symptoms(conversation_context)}"
    cached = _chat_cache_get(cache_key)
    if cached is not None:
        return cached

    include_access_policy = not bool((conversation_context or "").strip())

    # ---- Web search for general / knowledge questions ----
    web_context = ""
    _lower = normalized.replace("?", " ").strip()
    _is_general_question = (
        any(kw in _lower for kw in ("what is", "what are", "who is", "how does", "how do", "when did", "where is", "define", "explain", "tell me about", "meaning of"))
        or (len(_lower.split()) >= 3 and "?" in user_message)
    )
    if _is_general_question:
        web_context = await web_search(user_message)

    fallback_core = (
        "Hey colleague, happy to help. Based on what you've shared so far I'd keep things practical: "
        "refine the working differentials with focused history/exam, and escalate only when objective findings support it. "
        "Let me know what you're working with and I'll dig in."
    )
    fallback_text = _sanitize_physician_chat_response(fallback_core, include_access_policy=include_access_policy)

    api_key = settings.groq_api_key
    if not api_key:
        return fallback_text

    prompt = (
        "You are Pulse, a friendly and knowledgeable senior physician assistant used only by doctors. "
        "The user is a clinician. Respond in a warm, professional but approachable tone — like a helpful colleague. "
        "Keep answers concise but adequate (3-5 sentences for typical queries, more if user explicitly asks for detail). "
        "Do NOT use any structured template, JSON, or Condition/Confidence/Risk fields. "
        "For clinical questions: give differential-oriented reasoning, risk stratification, and practical next steps. "
        "For general knowledge questions: give a clear, accurate answer using provided web search context if available. "
        "For casual messages (hi/hello/good morning): respond warmly and ask what clinical scenario they'd like help with. "
        "Do not repeat access-policy language on every reply.\n\n"
    )
    if web_context:
        prompt += f"Web search context (use to ground your answer): {web_context}\n\n"
    if conversation_context:
        prompt += f"Previous conversation context: {conversation_context}\n\n"
    prompt += f"User message: {user_message}"

    payload = {
        "model": settings.groq_model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": "You are Pulse, a friendly senior physician assistant for doctors only. Reply in plain text paragraphs. Be warm, concise, and helpful."},
            {"role": "user", "content": prompt},
        ],
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        timeout = httpx.Timeout(20.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        content = _sanitize_physician_chat_response(
            data["choices"][0]["message"]["content"],
            include_access_policy=include_access_policy,
        )
        _chat_cache_set(cache_key, content)
        return content
    except Exception:
        return fallback_text
