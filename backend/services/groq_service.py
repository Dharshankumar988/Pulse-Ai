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
_CHAT_PROMPT_VERSION = "v6"
_SYMPTOM_PROMPT_VERSION = "v3"


def _safe_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_funny_or_nonsense(text: str) -> bool:
    """Detect humorous, absurd, or obviously non-medical prompts."""
    lower = text.lower().strip()
    funny_patterns = [
        r"\b(joke|funny|lol|lmao|rofl|haha|hehe|xd|bruh)\b",
        r"\b(zombie|vampire|werewolf|alien|unicorn|dragon|wizard)\b",
        r"\b(bitten by.*spider|superhero|superpow|x-ray vision|laser eyes)\b",
        r"\b(immortal|invincible|fly|flying|teleport)\b",
        r"\b(banana|pizza|taco|burger)\s+(disease|syndrome|infection)\b",
        r"\bmy\s+(cat|dog|hamster|fish|parrot)\s+(is|has|feels)\b",
        r"\b(love\s*sick|broken\s*heart\s*syndrome|allergic\s*to\s*(monday|work|school|homework))\b",
        r"\b(cure\s*for\s*(boredom|laziness|stupidity|ugliness|monday))\b",
        r"\b(diagnose\s*my\s*(ex|boss|teacher|neighbor))\b",
    ]
    for pattern in funny_patterns:
        if re.search(pattern, lower):
            return True
    # Very short nonsense
    if len(lower.split()) <= 2 and not any(c.isalpha() for c in lower):
        return True
    return False


def _build_humorous_response(prompt: str) -> dict:
    """Build a witty response for funny/nonsense prompts."""
    lower = prompt.lower()
    if "zombie" in lower:
        quip = "Zombie bite? Unfortunately that's outside my formulary. I'd recommend running faster next time. But seriously — if you have a real wound, let's talk wound care!"
    elif "spider" in lower and "bit" in lower:
        quip = "With great power comes great responsibility... to still see a real doctor. No radioactive spider antidote in stock, but if it's an actual spider bite, I can help with that!"
    elif "love" in lower and "sick" in lower:
        quip = "Lovesickness — the one condition where the cure is worse than the disease! Medically speaking though, if you're feeling chest tightness or anxiety, those are real symptoms worth discussing."
    elif "cat" in lower or "dog" in lower or "hamster" in lower:
        quip = "I appreciate the concern for your furry friend! I'm trained for human medicine though. A vet would be your best bet. Got any human symptoms I can help with?"
    elif "monday" in lower or "boredom" in lower or "laziness" in lower:
        quip = "Ah yes, a classic case of Mondayitis! Sadly not in the ICD-11 yet. But if you're feeling persistent fatigue or low mood, that's worth a real conversation."
    elif "broken heart" in lower:
        quip = "Takotsubo cardiomyopathy (broken heart syndrome) IS actually real! Stress-induced cardiomyopathy. If you're experiencing chest pain, that's worth investigating seriously."
    else:
        quip = "Ha! That's a creative one. I'm built for real clinical scenarios though — symptoms, images, differentials. Got something medical I can sink my teeth into?"
    return {
        "disease": "humor_detected",
        "probability": 0.0,
        "severity": "low",
        "risk": "low",
        "missing_inputs": [],
        "follow_up_questions": ["Got any real symptoms you'd like me to analyze?"],
        "clinical_reasoning": quip,
        "summary": quip,
        "source": "humor",
    }


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
    elif "rash" in text or "itch" in text or "skin" in text:
        disease = "dermatological_condition_suspected"
        severity = "moderate"
        risk = "medium"
        probability = 0.60
    elif "breath" in text or "wheez" in text or "asthma" in text:
        disease = "respiratory_condition_suspected"
        severity = "high"
        risk = "high"
        probability = 0.70
    elif "chest" in text and "pain" in text:
        disease = "acute_chest_pain_syndrome"
        severity = "critical"
        risk = "high"
        probability = 0.80
    elif "dizz" in text or "vertigo" in text or "faint" in text:
        disease = "vestibular_or_presyncope_syndrome"
        severity = "moderate"
        risk = "medium"
        probability = 0.58
    elif "burn" in text and ("urin" in text or "pee" in text):
        disease = "urinary_tract_infection_suspected"
        severity = "moderate"
        risk = "medium"
        probability = 0.72
    elif "headache" in text and ("severe" in text or "worst" in text or "thunder" in text):
        disease = "severe_headache_syndrome_rule_out_SAH"
        severity = "critical"
        risk = "high"
        probability = 0.75
    elif "diabetes" in text or ("thirst" in text and "frequent" in text and "urin" in text):
        disease = "diabetes_mellitus_suspected"
        severity = "high"
        risk = "high"
        probability = 0.70
    elif "depression" in text or "suicid" in text or "hopeless" in text:
        disease = "major_depressive_disorder_suspected"
        severity = "critical"
        risk = "high"
        probability = 0.72
    elif "anxiety" in text or "panic" in text or "palpitat" in text:
        disease = "anxiety_disorder_or_panic_disorder"
        severity = "moderate"
        risk = "medium"
        probability = 0.65

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
    context = image_context or {}
    context_condition = str(context.get("image_condition") or "").strip()
    context_probability = max(0.0, min(1.0, _safe_float(context.get("image_confidence"), 0.35)))
    fallback_disease = context_condition if context_condition and context_condition.lower() not in {"unknown", "unknown_condition", "unknown condition"} else "unclassified_image_finding"
    fallback_probability = context_probability if context_probability > 0.0 else 0.35

    fallback_output = {
        "disease": fallback_disease,
        "probability": fallback_probability,
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
        "You are Pulse, an expert medical image analysis AI for physicians. "
        "IMPORTANT: Analyze the ACTUAL content of this image thoroughly. Do NOT give generic responses. "
        "If the image shows a medical condition (X-ray, CT, skin photo, etc.), identify the SPECIFIC condition visible. "
        "If the image is NOT a standard medical image (e.g., a photo of food, a person, scenery, an object), "
        "describe what you actually see and explain that it doesn't appear to be a medical image, but note any "
        "health-relevant observations if applicable. "
        "If the image quality is poor or ambiguous, say so specifically rather than guessing. "
        "Return ONLY valid JSON using this schema: "
        "{"
        "\"disease\": string (be SPECIFIC — e.g., 'distal radius fracture' not just 'fracture', 'contact dermatitis' not just 'skin condition'),"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"follow_up_questions\": string[] (max 4, phrased for clinicians),"
        "\"clinical_reasoning\": string (max 100 words, describe what you ACTUALLY see in the image),"
        "\"summary\": string (max 40 words),"
        "\"source\": \"groq_vision\""
        "}."
        f"\nSymptoms/clinical context: {symptoms or 'not provided'}"
        f"\nImage context: {context_text}"
    )

    payload = {
        "model": settings.groq_vision_model,
        "temperature": 0.15,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are an expert medical image analysis AI. Analyze images thoroughly and describe what you ACTUALLY see. If the image is not a medical image, say so. If it shows a non-standard condition, describe the visual findings specifically. Never give generic responses."},
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
        "You are Pulse, an expert clinical pharmacology and treatment AI for physicians. "
        "Based on the image, suspected condition, and symptoms, provide SPECIFIC, EVIDENCE-BASED treatment recommendations. "
        "CRITICAL RULES: "
        "1. Do NOT default to just paracetamol/ibuprofen unless that is truly the first-line treatment for THIS specific condition. "
        "2. Recommend the ACTUAL first-line drug that targets this specific condition's pathophysiology. "
        "Examples: amoxicillin for bacterial pneumonia, metformin for type 2 diabetes, salbutamol for acute asthma, "
        "fluconazole for fungal infections, topical corticosteroids for eczema, ACE inhibitors for heart failure. "
        "3. Include the drug class, typical adult dose range, and route when relevant. "
        "Return ONLY valid JSON with this schema: "
        "{"
        "\"disease_key\": string,"
        "\"drugs\": string[] (SPECIFIC drugs that treat THIS condition, not generic painkillers unless appropriate),"
        "\"procedures\": string[],"
        "\"tests\": string[],"
        "\"doctor_note\": string (max 100 words, experienced and reassuring clinical tone with specific reasoning),"
        "\"source\": \"groq_vision\""
        "}. "
        "The doctor_note must sound like an experienced senior clinician: clear, calm, practical, and safety-focused."
        f"\nCondition: {condition or 'unknown'}"
        f"\nSymptoms: {symptoms or 'not provided'}"
    )

    payload = {
        "model": settings.groq_vision_model,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": "You are an expert clinical pharmacology AI. Output SPECIFIC, evidence-based treatment JSON. Never default to paracetamol/ibuprofen unless truly first-line for the exact condition. Name specific drugs with doses."},
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
                {"role": "system", "content": "You are an expert clinical pharmacology AI. Output SPECIFIC, evidence-based treatment JSON. Never default to paracetamol/ibuprofen unless truly first-line for the exact condition."},
                {
                    "role": "user",
                    "content": (
                        "Generate SPECIFIC treatment recommendations for suspected medical condition. "
                        "Return ONLY JSON schema: {\"disease_key\":string,\"drugs\":string[],\"procedures\":string[],\"tests\":string[],\"doctor_note\":string,\"source\":\"groq\"}. "
                        "The drugs MUST target the specific condition's pathophysiology. Do NOT just suggest paracetamol/ibuprofen. "
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

    web_context = await web_search(f"first-line drug treatment evidence-based guidelines for: {symptoms or condition}")
    web_context_text = web_context or "No external web snippet available. Use evidence-based, guideline-concordant clinical reasoning. Do NOT default to generic analgesics."

    prompt = (
        "You are Pulse, an expert clinical pharmacology AI for physicians. "
        "You MUST recommend SPECIFIC, EVIDENCE-BASED drugs that directly treat the identified condition. "
        "\n\nCRITICAL DRUG SELECTION RULES: "
        "- Do NOT default to paracetamol or ibuprofen unless they are genuinely the first-line treatment for THIS condition. "
        "- Analyze the condition's pathophysiology and recommend the drug that TARGETS it. "
        "- For INFECTIONS: recommend the appropriate antibiotic/antifungal/antiviral (e.g., amoxicillin-clavulanate for bacterial sinusitis, fluconazole for candidiasis, oseltamivir for influenza). "
        "- For INFLAMMATORY conditions: recommend condition-specific anti-inflammatories (e.g., colchicine for gout, topical betamethasone for eczema, montelukast for asthma). "
        "- For CHRONIC conditions: recommend disease-modifying agents (e.g., metformin for T2DM, lisinopril for hypertension, sertraline for depression). "
        "- For ACUTE conditions: recommend targeted acute management (e.g., salbutamol for bronchospasm, ondansetron for vomiting, sumatriptan for migraine). "
        "- Only use paracetamol/ibuprofen as adjunct analgesics when pain management is a secondary goal. "
        "- Include typical adult dose range and route for primary_drug. "
        "\n\nReturn ONLY valid JSON using this exact schema: "
        "{"
        "\"disease_key\": string,"
        "\"primary_drug\": string (the MOST SPECIFIC drug for this condition with dose),"
        "\"drugs\": string[] (primary + supportive drugs, max 4),"
        "\"alternative_drugs\": string[] (alternatives if primary is contraindicated),"
        "\"safety_cautions\": string[],"
        "\"procedures\": string[],"
        "\"tests\": string[],"
        "\"doctor_note\": string (max 100 words, practical and safety-focused with specific clinical reasoning),"
        "\"source\": \"groq\""
        "}. "
        f"Condition hint: {condition or 'general_non_specific_finding'}. "
        f"Risk level: {risk_level or 'medium'}. "
        f"Symptoms: {symptoms or 'not provided'}. "
        f"Web search context (use for evidence-based drug selection): {web_context_text}"
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
            "temperature": 0.15,
            "response_format": {"type": "json_object"},
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Return JSON only. No prose. You MUST recommend SPECIFIC drugs that target the condition's pathophysiology. "
                        "Do NOT default to paracetamol/ibuprofen unless truly indicated. "
                        "Schema keys required: disease_key, primary_drug, drugs, alternative_drugs, safety_cautions, procedures, tests, doctor_note, source."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Return strict JSON only for physician-facing treatment recommendations. "
                        "The primary_drug MUST be the specific first-line drug for this EXACT condition (e.g., amoxicillin for bacterial pharyngitis, NOT paracetamol). "
                        f"Condition: {condition or 'general_non_specific_finding'}. "
                        f"Risk: {risk_level or 'medium'}. "
                        f"Symptoms: {symptoms or 'not provided'}. "
                        f"Web evidence: {web_context_text}"
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
        uti_markers = {"urinary", "burning", "urine", "frequency", "dysuria", "uti"}
        skin_markers = {"rash", "itch", "eczema", "dermatitis", "fungal", "infection"}
        headache_markers = {"headache", "migraine"}
        asthma_markers = {"wheez", "asthma", "bronchospasm", "breathless"}
        diabetes_markers = {"diabetes", "blood sugar", "hyperglycemia"}
        hypertension_markers = {"hypertension", "high blood pressure", "bp"}
        depression_markers = {"depression", "depressed", "anxiety", "panic"}
        allergy_markers = {"allergy", "allergic", "hives", "urticaria", "anaphylaxis"}
        infection_markers = {"infection", "infected", "pus", "abscess", "cellulitis"}

        if any(marker in combined for marker in uti_markers):
            return ["nitrofurantoin 100mg BD x5 days (first-line for uncomplicated UTI)", "trimethoprim 200mg BD x3 days (alternative)"]
        if any(marker in combined for marker in skin_markers) and "fungal" in combined:
            return ["clotrimazole 1% cream BD x2-4 weeks (topical antifungal)", "fluconazole 150mg single dose (if extensive)"]
        if any(marker in combined for marker in skin_markers):
            return ["betamethasone 0.1% cream BD (topical corticosteroid)", "cetirizine 10mg OD (antihistamine for itch)"]
        if any(marker in combined for marker in asthma_markers):
            return ["salbutamol 100mcg MDI 2 puffs PRN (bronchodilator)", "prednisolone 40mg OD x5 days (if acute exacerbation)"]
        if any(marker in combined for marker in headache_markers) and "migraine" in combined:
            return ["sumatriptan 50-100mg PO (triptan for acute migraine)", "metoclopramide 10mg (if nausea present)"]
        if any(marker in combined for marker in diabetes_markers):
            return ["metformin 500mg BD (titrate up, first-line T2DM)", "gliclazide 40mg OD (if additional glycemic control needed)"]
        if any(marker in combined for marker in hypertension_markers):
            return ["amlodipine 5mg OD (CCB first-line)", "lisinopril 10mg OD (ACE inhibitor alternative)"]
        if any(marker in combined for marker in depression_markers):
            return ["sertraline 50mg OD (SSRI first-line)", "escitalopram 10mg OD (alternative SSRI)"]
        if any(marker in combined for marker in allergy_markers):
            return ["cetirizine 10mg OD (second-gen antihistamine)", "prednisolone 30-40mg (if severe allergic reaction)"]
        if any(marker in combined for marker in infection_markers):
            return ["amoxicillin-clavulanate 625mg TDS (broad-spectrum antibiotic)", "flucloxacillin 500mg QDS (if skin/soft tissue)"]
        if any(marker in combined for marker in gi_markers):
            return ["ondansetron 4mg PO/SL (antiemetic)", "pantoprazole 40mg OD (PPI for gastric protection)"]
        if any(marker in combined for marker in pain_markers):
            return ["naproxen 500mg BD (NSAID, better sustained analgesia)", "diclofenac 50mg TDS (alternative NSAID)"]
        if any(marker in combined for marker in respiratory_markers):
            return ["amoxicillin 500mg TDS x5-7d (if bacterial suspected)", "dextromethorphan 30mg QDS (antitussive for dry cough)"]
        if any(marker in combined for marker in gastric_markers):
            return ["pantoprazole 40mg OD (PPI)", "ranitidine 150mg BD (H2 blocker alternative)"]
        return ["clinical assessment needed before drug recommendation"]

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
    # ---- Humor detection ----
    if _is_funny_or_nonsense(symptoms):
        return _build_humorous_response(symptoms)

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

    web_context = await web_search(f"medical diagnosis differential treatment first-line drug for: {symptoms}")
    web_context_text = web_context or "No web snippets available; use conservative clinical triage reasoning with specific differential diagnosis."

    prompt = (
        "You are Pulse, an expert medical triage AI for physician users. Given symptoms, perform a THOROUGH differential diagnosis. "
        "CRITICAL RULES: "
        "1. Analyze ALL symptoms together to identify the most likely SPECIFIC condition — not just 'non-specific condition'. "
        "2. Use the web search context below to ground your reasoning in current medical evidence. "
        "3. Consider symptom combinations, duration, severity, and risk factors holistically. "
        "4. Provide a SPECIFIC disease name (e.g., 'acute bacterial sinusitis' not just 'infection', 'gout' not just 'joint pain'). "
        "5. Your clinical_reasoning MUST explain WHY you arrived at this specific diagnosis based on the symptom pattern. "
        "Return ONLY valid JSON and no markdown. "
        "Do NOT provide medications, drugs, dosages, procedures, or test recommendations. "
        "Only provide diagnostic triage fields defined below. "
        "Use this exact schema: "
        "{"
        "\"disease\": string (SPECIFIC diagnosis, not generic),"
        "\"probability\": number(0-1),"
        "\"severity\": \"low\"|\"moderate\"|\"high\"|\"critical\","
        "\"risk\": \"low\"|\"medium\"|\"high\","
        "\"missing_inputs\": string[],"
        "\"follow_up_questions\": string[] (max 4 concise clinician-facing questions that would help narrow the differential),"
        "\"clinical_reasoning\": string (max 100 words, explain the diagnostic reasoning connecting symptoms to the identified condition),"
        "\"summary\": string (max 40 words),"
        "\"source\": \"groq\""
        "}."
        "\nWeb context (latest evidence; use to support your differential diagnosis): "
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
    Handles humorous prompts with wit.
    """
    # ---- Humor detection ----
    if _is_funny_or_nonsense(user_message):
        humor = _build_humorous_response(user_message)
        return humor["summary"]

    normalized = _normalize_symptoms(user_message)
    cache_key = f"chat::{_CHAT_PROMPT_VERSION}::{normalized}::{_normalize_symptoms(conversation_context)}"
    cached = _chat_cache_get(cache_key)
    if cached is not None:
        return cached

    include_access_policy = not bool((conversation_context or "").strip())

    # ---- Web search for ANY question that needs real info ----
    web_context = ""
    _lower = normalized.replace("?", " ").strip()
    _is_general_question = (
        any(kw in _lower for kw in ("what is", "what are", "who is", "how does", "how do", "when did", "where is", "define", "explain", "tell me about", "meaning of"))
        or (len(_lower.split()) >= 3 and "?" in user_message)
    )
    _is_medical_question = any(kw in _lower for kw in (
        "drug", "dose", "dosage", "treatment", "side effect", "interact", "contraindic",
        "antibiotic", "prescri", "diagnos", "symptom", "disease", "condition", "syndrome",
        "therapy", "mechanism", "pathophys", "prognosis", "complication"
    ))
    if _is_general_question or _is_medical_question:
        web_context = await web_search(user_message)
    # Also search if the message is longer (likely asking something substantive)
    if not web_context and len(_lower.split()) >= 5:
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
        "You are Pulse, a friendly, knowledgeable, and sometimes witty senior physician assistant used only by doctors. "
        "The user is a clinician. Respond in a warm, professional but approachable tone — like a helpful colleague. "
        "IMPORTANT RULES: "
        "1. Keep answers concise but adequate (3-5 sentences for typical queries, more if user explicitly asks for detail). "
        "2. Do NOT use any structured template, JSON, or Condition/Confidence/Risk fields. "
        "3. For clinical questions: give differential-oriented reasoning, risk stratification, and practical next steps. Use web search context for evidence-based answers. "
        "4. For drug/treatment questions: be SPECIFIC with drug names, doses, mechanisms. Don't just say 'an antibiotic' — name the specific one. "
        "5. For general knowledge questions: give a clear, accurate answer using web search context. "
        "6. For casual messages (hi/hello/good morning): respond warmly and ask what clinical scenario they'd like help with. "
        "7. For funny/humorous messages: respond with wit and humor! Be playful but still professional. A doctor's sense of humor is welcome. "
        "8. NEVER give generic responses. Every answer should feel researched and specific. "
        "Do not repeat access-policy language on every reply.\n\n"
    )
    if web_context:
        prompt += f"Web search context (use to ground your answer with real, current information): {web_context}\n\n"
    if conversation_context:
        prompt += f"Previous conversation context: {conversation_context}\n\n"
    prompt += f"User message: {user_message}"

    payload = {
        "model": settings.groq_model,
        "temperature": 0.35,
        "messages": [
            {"role": "system", "content": "You are Pulse, a friendly, witty, and deeply knowledgeable senior physician assistant for doctors only. Reply in plain text paragraphs. Be warm, specific, evidence-based, and occasionally humorous when appropriate."},
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
