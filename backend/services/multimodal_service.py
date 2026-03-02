from io import BytesIO
import re

from PIL import Image

from config.settings import settings
from services.groq_service import (
    analyze_image_with_groq,
    analyze_symptoms_with_groq,
    analyze_uncertain_image_with_groq,
    chat_followup_with_groq,
    generate_recommendations_with_groq,
)
from services.knowledge_base_service import KnowledgeBaseError, get_recommendations_for_disease
from services.ml_service import MLServiceError, get_model_name_for_task, run_routed_image_analysis


def _clip_probability(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _risk_from_confidence(confidence: float) -> str:
    if confidence >= 0.8:
        return "high"
    if confidence >= 0.5:
        return "medium"
    return "low"


def _build_veteran_doctor_note(condition: str, risk_level: str, symptoms: str) -> str:
    condition_text = str(condition or "a non-specific finding").replace("_", " ").strip()
    symptoms_text = str(symptoms or "").strip()
    if "current=" in symptoms_text:
        symptoms_text = symptoms_text.split("current=", 1)[1].strip()
    symptoms_text = re.sub(r"\b(history|conversation|current)\s*=", "", symptoms_text, flags=re.IGNORECASE)
    symptoms_text = re.sub(r"\s*\|\s*", " ", symptoms_text).strip()
    if not symptoms_text:
        symptoms_text = "no clear symptom progression provided"
    risk_text = str(risk_level or "medium").lower()

    return (
        f"This pattern is most consistent with {condition_text}. "
        f"Risk level: {risk_text} — I'd recommend a stepwise approach: stabilize, monitor for deterioration, "
        f"and escalate if red-flag signs emerge. "
        f"Clinical context: {symptoms_text[:160]}."
    )


def _is_unknown_condition(value: str | None) -> bool:
    normalized = str(value or "").strip().lower().replace("_", " ")
    return normalized in {
        "",
        "unknown",
        "unknown condition",
        "unknown class",
        "class 0",
        "class 1",
        "class 2",
        "general non specific finding",
    }


def _is_followup_chat(symptoms_text: str) -> bool:
    """Detect if the user message is a follow-up/conversational question rather than initial symptom reporting.

    Returns True when the message looks like a conversational follow-up (e.g. asking for
    alternative drugs, clarifying questions, general medical queries) and does NOT look
    like a fresh symptom description that should trigger the full analysis template.
    """
    if not symptoms_text:
        return False

    # Extract the "current=" portion which is what the user actually typed right now
    current_text = symptoms_text
    if "current=" in symptoms_text:
        current_text = symptoms_text.split("current=")[-1].strip()
    # If there is no current text, it's not a follow-up
    if not current_text:
        return False

    lower = current_text.lower().strip()
    normalized_lower = re.sub(r"[^a-z0-9\s]", " ", lower)
    normalized_lower = " ".join(normalized_lower.split())

    # Greetings/small-talk should never trigger disease analysis.
    greeting_tokens = {
        "hi", "hello", "hey", "hii", "helo", "yo", "sup", "good morning", "good afternoon", "good evening",
        "good night", "howdy", "hey there", "hi there", "hello there",
        "how are you", "how r u", "whats up", "what s up",
        "thanks", "thank you", "ok", "okay", "alright", "fine",
    }
    if normalized_lower in greeting_tokens:
        return True

    # Check if there is conversation context (indicates this is NOT the first message)
    has_conversation_context = "conversation=" in symptoms_text

    # If there's no conversation context, this is likely the first message - treat as analysis
    if not has_conversation_context:
        return False

    # Patterns that indicate a follow-up / conversational question
    followup_indicators = [
        # Asking for alternatives
        "alternative", "another drug", "better drug", "different drug", "other drug",
        "alternate drug", "alternate medicine", "alternate medication",
        "other medication", "another medication", "different medication", "substitute",
        "replacement", "instead of", "switch to", "can you suggest", "can u suggest",
        "give me a better", "give me another", "give me an alternate", "recommend another", "what else",
        # Asking about something
        "what is", "what are", "what about", "how about", "how does", "how do",
        "how long", "how much", "how often", "can i", "can you", "could you",
        "should i", "is it", "is there", "are there", "do i", "does it",
        "tell me", "explain", "why", "when should",
        # Thank you / acknowledgement
        "thank", "thanks", "ok", "okay", "got it", "understood",
        # General conversational
        "more info", "more details", "more about", "elaborate",
        "what do you think", "your opinion", "side effect", "side effects",
        "dosage", "how to take", "precaution", "contraindication",
        "interact", "interaction",
    ]

    for indicator in followup_indicators:
        if indicator in normalized_lower:
            return True

    # Short messages with a question mark are likely follow-ups
    if "?" in current_text and len(current_text.split()) <= 20:
        return True

    return False


def _extract_current_and_context(symptoms_text: str) -> tuple[str, str]:
    """Split the symptoms string into (current_user_message, conversation_context)."""
    current = symptoms_text
    context = ""
    if "current=" in symptoms_text:
        parts = symptoms_text.split("current=", 1)
        context = parts[0].strip().rstrip("|").strip()
        current = parts[1].strip()
    return current, context


def _looks_like_symptom_report(text: str) -> bool:
    candidate = (text or "").strip().lower()
    if not candidate:
        return False

    normalized = re.sub(r"[^a-z0-9\s]", " ", candidate)
    normalized = " ".join(normalized.split())

    greeting_tokens = {
        "hi", "hello", "hey", "hii", "helo", "yo", "sup", "good morning", "good afternoon", "good evening",
        "good night", "howdy", "hey there", "hi there", "hello there",
        "how are you", "how r u", "whats up", "what s up",
        "thanks", "thank you", "ok", "okay", "alright", "fine",
    }
    if normalized in greeting_tokens:
        return False

    symptom_keywords = {
        "pain", "fever", "cough", "cold", "headache", "nausea", "vomit", "vomiting", "diarrhea",
        "dizziness", "fatigue", "weakness", "swelling", "bleeding", "rash", "itching", "breathless",
        "breathlessness", "shortness", "chest", "abdomen", "stomach", "throat", "ear", "eye", "back",
        "knee", "ankle", "wrist", "urine", "urinary", "burning", "painful", "injury", "fracture",
        "lump", "mass", "stone", "infection", "sore", "unconscious", "fainting", "seizure", "bp",
    }

    report_markers = {"since", "for", "days", "day", "weeks", "week", "months", "month", "started", "worsening", "worse"}

    tokens = set(normalized.split())
    if tokens & symptom_keywords:
        return True
    if tokens & report_markers and len(tokens) >= 3:
        return True
    if any(ch.isdigit() for ch in normalized) and ("day" in tokens or "week" in tokens or "month" in tokens):
        return True

    return False


def _is_alternate_drug_request(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())
    normalized = " ".join(normalized.split())
    phrases = {
        "alternate drug",
        "alternative drug",
        "another drug",
        "different drug",
        "other drug",
        "alternate medicine",
        "alternative medicine",
        "another medication",
        "different medication",
        "drug alternative",
    }
    if normalized in phrases:
        return True
    return any(phrase in normalized for phrase in phrases)


def _infer_condition_from_context(current_text: str, context_text: str) -> str | None:
    merged = f"{context_text} | {current_text}".lower()

    direct_patterns = [
        r"condition\s*=\s*([a-z_\- ]+)",
        r"analysis\s*:\s*([a-z_\- ]+)",
        r"diagnosis\s*:\s*([a-z_\- ]+)",
    ]
    for pattern in direct_patterns:
        match = re.search(pattern, merged)
        if match and match.group(1).strip():
            return match.group(1).strip()

    keyword_map = {
        "fracture": "fracture",
        "distal radius": "fracture",
        "radius fracture": "fracture",
        "kidney stone": "kidney_stone",
        "renal stone": "kidney_stone",
        "stone": "kidney_stone",
        "tumor": "tumor",
        "mass": "tumor",
        "skin": "skin_condition",
        "dermat": "skin_condition",
    }
    for key, value in keyword_map.items():
        if key in merged:
            return value
    return None


def _build_alternate_drug_response(condition_hint: str | None, recommendation: dict | None) -> str:
    if not recommendation:
        return (
            "Happy to help with an alternate drug! I just need a bit more context — "
            "share the target condition or current medication class, reason for switching (intolerance, resistance, ADR), "
            "and any constraints (renal/hepatic function, bleeding risk, key interactions). "
            "That way I can give you a grounded recommendation."
        )

    primary = (recommendation.get("drugs") or [""])[0]
    alternatives = recommendation.get("alternative_drugs") or []
    cautions = recommendation.get("safety_cautions") or []
    refs = recommendation.get("guideline_sources") or []
    condition_text = str(condition_hint or recommendation.get("disease_key") or "target condition").replace("_", " ").strip()

    alt_text = ", ".join(str(item) for item in alternatives[:2]) if alternatives else "no alternate listed in current guidelines"
    caution_text = "; ".join(str(item) for item in cautions[:2]) if cautions else "standard contraindication and interaction checks apply"
    refs_text = "; ".join(str(item) for item in refs[:2]) if refs else "internal knowledge-base"

    return (
        f"For **{condition_text}**, here's what I'd suggest:\n\n"
        f"- **Current first-line:** {primary or 'not mapped'}\n"
        f"- **Alternatives:** {alt_text}\n"
        f"- **Safety check:** {caution_text}\n"
        f"- **Source:** {refs_text}\n\n"
        "Let me know if you need dosing details or have specific patient constraints to factor in."
    )


def _is_stronger_drug_request(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())
    normalized = " ".join(normalized.split())
    triggers = [
        "stronger drug",
        "stronger medicine",
        "stronger medication",
        "more potent drug",
        "more potent medicine",
        "increase potency",
        "stronger option",
    ]
    return any(trigger in normalized for trigger in triggers)


def _is_casual_greeting(text: str) -> bool:
    normalized = re.sub(r"[^a-z0-9\s]", " ", str(text or "").lower())
    normalized = " ".join(normalized.split())
    greetings = {
        "hi", "hello", "hey", "hii", "helo", "yo", "sup",
        "good morning", "good evening", "good afternoon", "good night",
        "how are you", "how r u", "whats up", "what s up", "howdy",
        "hey there", "hi there", "hello there",
    }
    return normalized in greetings


def _build_stronger_drug_response(condition_hint: str | None, recommendation: dict | None) -> str:
    if not recommendation:
        return (
            "Sure, happy to help escalate! To recommend a stronger option I need:\n\n"
            "- **Target condition** and current drug/class\n"
            "- **Reason for escalation** (inadequate response, breakthrough symptoms)\n"
            "- **Constraints** (renal/hepatic function, bleeding risk, key interactions)\n\n"
            "Share those and I'll give you a specific recommendation."
        )

    primary = (recommendation.get("drugs") or [""])[0]
    alternatives = recommendation.get("alternative_drugs") or []
    cautions = recommendation.get("safety_cautions") or []
    refs = recommendation.get("guideline_sources") or []
    condition_text = str(condition_hint or recommendation.get("disease_key") or "target condition").replace("_", " ").strip()

    stronger = str(alternatives[0]) if alternatives else "No stronger mapped alternative in current guideline set"
    caution = str(cautions[0]) if cautions else "Apply contraindication and interaction checks before escalation"
    ref = str(refs[0]) if refs else "Internal guideline mapping"

    return (
        f"For **{condition_text}**, here's the escalation path:\n\n"
        f"- **Current first-line:** {primary or 'not mapped'}\n"
        f"- **Stronger option:** {stronger}\n"
        f"- **Safety check before switching:** {caution}\n"
        f"- **Source:** {ref}\n\n"
        "Need dosing specifics or want to factor in additional patient constraints? Just ask."
    )


def _is_skin_like_label(label: str | None) -> bool:
    text = str(label or "").strip().lower()
    skin_markers = {
        "fungal", "eczema", "acne", "psoriasis", "dermatitis", "skin", "lesion", "pimple", "hives", "itch"
    }
    return any(marker in text for marker in skin_markers)


def _harmonize_condition_with_detections(condition: str, confidence: float, detections: list[dict]) -> tuple[str, float]:
    if not detections:
        return condition, confidence

    top_detection = max(detections, key=lambda item: float(item.get("confidence", 0.0)))
    top_label = str(top_detection.get("label", "")).strip()
    top_conf = _clip_probability(float(top_detection.get("confidence", 0.0)))

    benign_or_non_specific = {
        "no apparent disease",
        "no anomaly",
        "no anomaly detected",
        "normal",
        "normal skin",
        "general_non_specific_finding",
        "general non specific finding",
        "unclassified_image_finding",
    }

    normalized_condition = str(condition or "").strip().lower().replace("_", " ")
    if not top_label or _is_unknown_condition(top_label):
        return condition, confidence

    if (normalized_condition in benign_or_non_specific or _is_unknown_condition(condition)) and top_conf >= 0.75:
        return top_label, max(confidence, top_conf)

    return condition, confidence


async def run_multimodal_pipeline(image_bytes: bytes | None, symptoms: str | None) -> dict:
    has_image = bool(image_bytes)
    cleaned_symptoms = (symptoms or "").strip()
    current_message, conversation_context = _extract_current_and_context(cleaned_symptoms)
    symptom_input = (current_message or cleaned_symptoms).strip()
    has_symptom_text = bool(symptom_input)

    if not has_image and not has_symptom_text:
        return {
            "response_type": "analysis",
            "chat_response": "",
            "condition": "insufficient_data",
            "confidence": 0.0,
            "risk_level": "low",
            "recommendation": {
                "drugs": [],
                "procedures": ["clinical assessment"],
                "tests": ["initial symptom screening"],
            },
            "notes": "Provide image and/or symptoms to continue analysis.",
            "needs_image": True,
            "needs_symptoms": True,
            "follow_up_questions": [
                "Provide the patient symptom profile with onset, duration, and progression.",
                "Upload relevant clinical imaging, if available, for correlation.",
            ],
            "detections": [],
            "image_width": None,
            "image_height": None,
        }

    # --- Text-only conversational handling (follow-up or general prompts) ---
    if not has_image and (_is_followup_chat(cleaned_symptoms) or not _looks_like_symptom_report(symptom_input)):
        if _is_casual_greeting(symptom_input):
            short_reply = (
                "Hey there, colleague! Welcome to Pulse. \n\n"
                "I'm here to help with clinical analysis, drug recommendations, differentials — whatever you need. "
                "Just share:\n"
                "- **Symptoms** you're evaluating\n"
                "- **An image** (X-ray, skin photo, scan) for AI-assisted analysis\n"
                "- Or **both** for the best results!\n\n"
                "What are you working on today?"
            )
            return {
                "response_type": "chat",
                "chat_response": short_reply,
                "condition": "",
                "confidence": 0.0,
                "risk_level": "low",
                "recommendation": {},
                "notes": "Friendly greeting with guidance on how to use the assistant.",
                "needs_image": False,
                "needs_symptoms": False,
                "follow_up_questions": [
                    "Describe the patient's symptoms and timeline.",
                    "Upload a clinical image for AI analysis.",
                    "Ask me any medical question — I can also search the web for you.",
                ],
                "detections": [],
                "image_width": None,
                "image_height": None,
            }

        if _is_alternate_drug_request(symptom_input):
            condition_hint = _infer_condition_from_context(symptom_input, conversation_context)
            recommendation = None
            if condition_hint:
                try:
                    recommendation = get_recommendations_for_disease(condition_hint, risk_level="medium")
                except KnowledgeBaseError:
                    recommendation = None

            alt_response = _build_alternate_drug_response(condition_hint, recommendation)
            return {
                "response_type": "chat",
                "chat_response": alt_response,
                "condition": "",
                "confidence": 0.0,
                "risk_level": "low",
                "recommendation": recommendation or {},
                "notes": "Condition-targeted alternate drug response.",
                "needs_image": False,
                "needs_symptoms": False,
                "follow_up_questions": [],
                "detections": [],
                "image_width": None,
                "image_height": None,
            }

        if _is_stronger_drug_request(symptom_input):
            condition_hint = _infer_condition_from_context(symptom_input, conversation_context)
            recommendation = None
            if condition_hint:
                try:
                    recommendation = get_recommendations_for_disease(condition_hint, risk_level="high")
                except KnowledgeBaseError:
                    recommendation = None

            stronger_response = _build_stronger_drug_response(condition_hint, recommendation)
            return {
                "response_type": "chat",
                "chat_response": stronger_response,
                "condition": "",
                "confidence": 0.0,
                "risk_level": "low",
                "recommendation": recommendation or {},
                "notes": "Condition-targeted stronger drug response.",
                "needs_image": False,
                "needs_symptoms": False,
                "follow_up_questions": [],
                "detections": [],
                "image_width": None,
                "image_height": None,
            }

        chat_text = await chat_followup_with_groq(symptom_input, conversation_context)
        return {
            "response_type": "chat",
            "chat_response": chat_text,
            "condition": "",
            "confidence": 0.0,
            "risk_level": "low",
            "recommendation": {},
            "notes": "Conversational follow-up response.",
            "needs_image": False,
            "needs_symptoms": False,
            "follow_up_questions": [],
            "detections": [],
            "image_width": None,
            "image_height": None,
        }

    image_condition = "unknown_condition"
    image_confidence = 0.0
    image_notes = ""
    image_mode = None
    routed_task = ""
    detections: list[dict] = []
    image_width: int | None = None
    image_height: int | None = None

    if has_image:
        try:
            with Image.open(BytesIO(image_bytes)) as image_obj:
                image_width, image_height = image_obj.size
        except Exception:
            image_width, image_height = None, None

        try:
            routed = run_routed_image_analysis(image_bytes, symptoms_hint=symptom_input)
            routed_task = str(routed.get("task") or "")
            image_condition = str(routed.get("condition", "unknown_condition"))
            image_confidence = _clip_probability(float(routed.get("confidence", 0.0)))
            image_mode = routed.get("mode")
            image_notes = str(routed.get("notes", ""))
            raw = routed.get("raw") or {}
            raw_predictions = raw.get("predictions") or []
            if routed.get("task") == "skin_classification" and raw_predictions:
                raw_predictions = [raw_predictions[0]]
            image_meta = raw.get("metadata") or {}
            image_width = int(image_meta.get("image_width")) if image_meta.get("image_width") else None
            image_height = int(image_meta.get("image_height")) if image_meta.get("image_height") else None
            for item in raw_predictions:
                bbox = item.get("bbox")
                if isinstance(bbox, list) and len(bbox) == 4:
                    detections.append(
                        {
                            "label": str(item.get("label", image_condition)),
                            "confidence": _clip_probability(float(item.get("confidence", 0.0))),
                            "bbox": [float(v) for v in bbox],
                            "is_estimated": bool(item.get("is_estimated", False)),
                        }
                    )
        except MLServiceError as exc:
            image_notes = f"Image routing failed: {exc}"

    symptom_condition = ""
    symptom_confidence = 0.0
    symptom_risk = ""
    symptom_summary = ""
    if has_symptom_text:
        symptom_result = await analyze_symptoms_with_groq(symptom_input)
        symptom_condition = str(symptom_result.get("disease", "")).strip()
        symptom_confidence = _clip_probability(float(symptom_result.get("probability", 0.0)))
        symptom_risk = str(symptom_result.get("risk", "")).strip().lower()
        symptom_summary = str(symptom_result.get("summary", "")).strip()

    if has_image and has_symptom_text:
        condition = image_condition if image_confidence >= symptom_confidence else (symptom_condition or image_condition)
        confidence = _clip_probability((image_confidence * 0.6) + (symptom_confidence * 0.4))
    elif has_image:
        condition = image_condition
        confidence = image_confidence
    else:
        condition = symptom_condition or "general_non_specific_finding"
        confidence = symptom_confidence

    if (
        not has_image
        and has_symptom_text
        and (
            _is_unknown_condition(condition)
            or condition in {"general_non_specific_finding", "insufficient symptom data", "non-specific condition"}
            or confidence < 0.45
        )
    ):
        chat_text = await chat_followup_with_groq(symptom_input, conversation_context)
        return {
            "response_type": "chat",
            "chat_response": chat_text,
            "condition": "",
            "confidence": 0.0,
            "risk_level": "low",
            "recommendation": {},
            "notes": "Conversational response used for non-specific text-only input.",
            "needs_image": False,
            "needs_symptoms": False,
            "follow_up_questions": [],
            "detections": [],
            "image_width": None,
            "image_height": None,
        }

    normalized_image_condition = str(image_condition or "").strip().lower().replace("_", " ")
    skin_non_specific_labels = {
        "skin condition",
        "benign skin finding",
        "unknown condition",
        "normal skin",
        "no anomaly",
        "no anomaly detected",
        "class 0",
        "class 1",
        "class 2",
    }
    non_skin_hint_keywords = {"fracture", "bone", "xray", "x-ray", "tumor", "stone", "kidney"}
    has_non_skin_hints = any(keyword in symptom_input.lower() for keyword in non_skin_hint_keywords)

    force_groq_for_uncertain_skin = (
        has_image
        and routed_task == "skin_classification"
        and (
            image_confidence < 0.65
            or normalized_image_condition in skin_non_specific_labels
            or _is_unknown_condition(image_condition)
            or has_non_skin_hints
        )
    )

    force_groq_for_rgb = has_image and image_mode == "color"

    fallback_used = False
    if has_image and (
        confidence < 0.7
        or _is_unknown_condition(condition)
        or force_groq_for_uncertain_skin
        or force_groq_for_rgb
    ):
        vision = await analyze_image_with_groq(
            image_bytes=image_bytes,
            symptoms=symptom_input if has_symptom_text else None,
            image_context={
                "image_mode": image_mode,
                "routed_task": routed_task,
                "image_condition": image_condition,
                "image_confidence": image_confidence,
                "threshold": 0.7,
                "forced_due_to_uncertain_skin": force_groq_for_uncertain_skin,
                "forced_due_to_rgb_image": force_groq_for_rgb,
            },
        )
        condition = str(vision.get("disease", condition or "skin condition")).strip() or "skin condition"
        confidence = _clip_probability(float(vision.get("probability", confidence)))
        image_notes = str(vision.get("summary", image_notes or "Image analyzed by Groq vision"))
        fallback_used = True

    if has_image and _is_unknown_condition(condition):
        condition = "unclassified_image_finding"
        fallback_used = True

    if has_image and image_mode == "color" and condition in {"unknown_condition", "general_non_specific_finding", "", "class_0", "class_1", "class_2"}:
        condition = "skin condition"

    if has_image and image_mode == "grayscale":
        detections = [item for item in detections if not _is_skin_like_label(item.get("label"))]
        if _is_skin_like_label(condition):
            condition = "unclassified_image_finding"
            confidence = min(confidence, 0.45)

    if has_image and detections:
        condition, confidence = _harmonize_condition_with_detections(condition, confidence, detections)

    if symptom_risk in {"low", "medium", "high"}:
        risk_level = symptom_risk
    else:
        risk_level = _risk_from_confidence(confidence)

    try:
        recommendation = get_recommendations_for_disease(condition, risk_level=risk_level)
    except KnowledgeBaseError:
        try:
            if has_image:
                recommendation = await generate_recommendations_with_groq(
                    image_bytes=image_bytes,
                    condition=condition,
                    symptoms=symptom_input if has_symptom_text else None,
                )
            else:
                raise KnowledgeBaseError("No grounded mapping for non-image condition")
        except Exception:
            recommendation = {
                "drugs": [],
                "alternative_drugs": [],
                "safety_cautions": ["No medication suggestion without condition-specific guideline match."],
                "procedures": ["clinical reassessment"],
                "tests": ["targeted diagnostic evaluation"],
                "guideline_sources": ["No matched guideline mapping"],
                "source": "knowledge_base_fallback",
            }

    drugs = recommendation.get("drugs") or []
    if isinstance(drugs, list) and drugs:
        recommendation["primary_drug"] = str(drugs[0])
        recommendation["drugs"] = [str(item) for item in drugs[:2]]
    else:
        recommendation["primary_drug"] = "No drug recommendation without condition-specific evidence"
        recommendation["drugs"] = []

    recommendation["doctor_note"] = str(
        recommendation.get("doctor_note")
        or _build_veteran_doctor_note(condition=condition, risk_level=risk_level, symptoms=symptom_input)
    ).strip()

    notes_parts = []
    if image_mode:
        notes_parts.append(f"image_mode={image_mode}")
    if image_notes:
        notes_parts.append(image_notes)
    if symptom_summary:
        notes_parts.append(f"symptoms={symptom_summary}")
    if fallback_used:
        notes_parts.append("Groq fallback applied due to unknown/low-confidence image analysis (<0.7).")

    notes = " | ".join(notes_parts) if notes_parts else "Analysis completed."

    if has_image and not detections and image_width and image_height:
        detections = [
            {
                "label": condition or image_condition or "suspected_finding",
                "confidence": confidence,
                "bbox": [
                    float(image_width * 0.2),
                    float(image_height * 0.2),
                    float(image_width * 0.8),
                    float(image_height * 0.8),
                ],
                "is_estimated": True,
            }
        ]

    follow_up_questions: list[str] = []
    needs_image = False
    needs_symptoms = False

    if has_image and not has_symptom_text:
        needs_symptoms = True
        follow_up_questions = [
            "Image analyzed; provide correlated patient symptoms and exam findings.",
            "Add symptom onset, progression, and any red-flag clinical changes.",
        ]
    elif has_symptom_text and not has_image:
        needs_image = True
        follow_up_questions = [
            "Upload relevant imaging to improve diagnostic confidence.",
            "If available, share a clearer close-up or alternate-view image for better interpretation.",
        ]

    _model_name = get_model_name_for_task(routed_task) if routed_task else ""

    return {
        "response_type": "analysis",
        "chat_response": "",
        "condition": condition or "general_non_specific_finding",
        "confidence": confidence,
        "risk_level": risk_level,
        "recommendation": recommendation,
        "notes": notes,
        "needs_image": needs_image,
        "needs_symptoms": needs_symptoms,
        "follow_up_questions": follow_up_questions,
        "detections": detections,
        "image_width": image_width,
        "image_height": image_height,
        "routed_task": routed_task,
        "model_name": _model_name,
    }
