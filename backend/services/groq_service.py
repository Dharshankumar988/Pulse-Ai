import json
import base64
import time

import httpx

from config.settings import settings


class GroqServiceError(RuntimeError):
    pass


_SYMPTOM_CACHE: dict[str, tuple[float, dict]] = {}
_UNCERTAINTY_CACHE: dict[str, tuple[float, dict]] = {}


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

    return {
        "disease": disease,
        "probability": probability,
        "severity": severity,
        "risk": risk,
        "missing_inputs": [],
        "follow_up_questions": [
            "How long have these symptoms been present?",
            "Are the symptoms getting better, worse, or unchanged?",
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
            "Can you share symptom duration and progression?",
            "Any fever, bleeding, or severe pain associated with this finding?",
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
        "You are Pulse, a medical triage assistant. Analyze the provided medical image and optional symptoms. "
        "Return ONLY valid JSON using this schema: "
        "{"
        "\"disease\": string,"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"follow_up_questions\": string[] (max 4),"
        "\"clinical_reasoning\": string (max 70 words),"
        "\"summary\": string (max 30 words),"
        "\"source\": \"groq_vision\""
        "}."
        f"\nSymptoms: {symptoms or 'not provided'}"
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


async def analyze_symptoms_with_groq(symptoms: str) -> dict:
    normalized_symptoms = _normalize_symptoms(symptoms)
    if not normalized_symptoms:
        return {
            "disease": "insufficient symptom data",
            "probability": 0.0,
            "severity": "low",
            "risk": "low",
            "missing_inputs": ["symptoms"],
            "follow_up_questions": ["Can you describe your key symptoms and when they started?"],
            "clinical_reasoning": "No symptom content was supplied.",
            "summary": "Symptom analysis skipped due to empty input.",
            "source": "empty-input",
        }

    cached = _cache_get(normalized_symptoms)
    if cached is not None:
        return {**cached, "source": "cache"}

    api_key = settings.groq_api_key
    if not api_key:
        fallback = _default_symptom_output(symptoms)
        _cache_set(normalized_symptoms, fallback)
        return fallback

    prompt = (
        "You are Pulse, a medical triage assistant. Given symptoms, return ONLY valid JSON and no markdown. "
        "Do NOT provide medications, drugs, dosages, procedures, or test recommendations. "
        "Only provide diagnostic triage fields defined below. "
        "Use this exact schema: "
        "{"
        "\"disease\": string,"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"missing_inputs\": string[],"
        "\"follow_up_questions\": string[] (max 4 concise questions),"
        "\"clinical_reasoning\": string (max 70 words),"
        "\"summary\": string (max 30 words),"
        "\"source\": \"groq\""
        "}."
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
        _cache_set(normalized_symptoms, structured)
        return structured
    except Exception as exc:
        fallback = _default_symptom_output(symptoms)
        fallback["summary"] = f"Groq unavailable, fallback used: {exc}"
        _cache_set(normalized_symptoms, fallback)
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
            "Can you provide a clearer image from another angle or modality?",
            "What are the key associated symptoms and their duration?",
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
        "You are Pulse, a medical triage assistant. An image analysis is uncertain. "
        "Do NOT provide medications, drugs, dosages, procedures, or test recommendations. "
        "Only provide uncertainty-aware diagnostic triage fields defined below. "
        "Return ONLY valid JSON with exact schema: "
        "{"
        "\"disease\": string,"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"uncertainty\": number(0-1),"
        "\"follow_up_questions\": string[] (max 4),"
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


async def chat_followup_with_groq(user_message: str, conversation_context: str = "") -> str:
    """Generate a conversational paragraph response for follow-up questions (no structured template)."""
    normalized = _normalize_symptoms(user_message)
    cache_key = f"chat::{normalized}::{_normalize_symptoms(conversation_context)}"
    cached = _chat_cache_get(cache_key)
    if cached is not None:
        return cached

    fallback_text = (
        "I'd be happy to help with your question. Based on what you've shared, "
        "I recommend discussing this with your treating physician who can review "
        "your full clinical picture and adjust the plan accordingly."
    )

    api_key = settings.groq_api_key
    if not api_key:
        return fallback_text

    prompt = (
        "You are Pulse, a helpful and knowledgeable medical assistant. "
        "The user is asking a follow-up question or having a general medical conversation. "
        "Respond naturally in 1-3 concise paragraphs. Do NOT use any structured template, "
        "do NOT output JSON, do NOT include fields like Condition/Confidence/Risk. "
        "Just answer the question helpfully and conversationally as a knowledgeable medical professional would. "
        "Be clear, practical, and safety-conscious. If recommending a drug, mention it naturally in the response. "
        "Always remind them to consult their physician for final decisions.\n\n"
    )
    if conversation_context:
        prompt += f"Previous conversation context: {conversation_context}\n\n"
    prompt += f"User question: {user_message}"

    payload = {
        "model": settings.groq_model,
        "temperature": 0.3,
        "messages": [
            {"role": "system", "content": "You are Pulse, a friendly and concise medical assistant. Respond in plain text paragraphs only."},
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
        content = data["choices"][0]["message"]["content"].strip()
        _chat_cache_set(cache_key, content)
        return content
    except Exception:
        return fallback_text
