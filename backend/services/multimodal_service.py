from io import BytesIO

from PIL import Image

from config.settings import settings
from services.groq_service import (
    analyze_image_with_groq,
    analyze_symptoms_with_groq,
    analyze_uncertain_image_with_groq,
    generate_recommendations_with_groq,
)
from services.knowledge_base_service import KnowledgeBaseError, get_recommendations_for_disease
from services.ml_service import MLServiceError, run_routed_image_analysis


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
    symptoms_text = str(symptoms or "no clear symptom progression provided").strip()
    risk_text = str(risk_level or "medium").lower()

    return (
        f"Based on the current pattern, this most closely fits {condition_text}. "
        f"Given the present risk level ({risk_text}), manage this in a stepwise way: stabilize symptoms, "
        f"watch for deterioration, and escalate promptly if red-flag signs appear. "
        f"Key clinical context considered: {symptoms_text[:160]}."
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


async def run_multimodal_pipeline(image_bytes: bytes | None, symptoms: str | None) -> dict:
    has_image = bool(image_bytes)
    cleaned_symptoms = (symptoms or "").strip()

    if not has_image and not cleaned_symptoms:
        return {
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
                "Please describe your symptoms and when they started.",
                "Please upload a relevant medical image if available.",
            ],
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
            routed = run_routed_image_analysis(image_bytes, symptoms_hint=cleaned_symptoms)
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
    if cleaned_symptoms:
        symptom_result = await analyze_symptoms_with_groq(cleaned_symptoms)
        symptom_condition = str(symptom_result.get("disease", "")).strip()
        symptom_confidence = _clip_probability(float(symptom_result.get("probability", 0.0)))
        symptom_risk = str(symptom_result.get("risk", "")).strip().lower()
        symptom_summary = str(symptom_result.get("summary", "")).strip()

    if has_image and cleaned_symptoms:
        condition = image_condition if image_confidence >= symptom_confidence else (symptom_condition or image_condition)
        confidence = _clip_probability((image_confidence * 0.6) + (symptom_confidence * 0.4))
    elif has_image:
        condition = image_condition
        confidence = image_confidence
    else:
        condition = symptom_condition or "general_non_specific_finding"
        confidence = symptom_confidence

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
    has_non_skin_hints = any(keyword in cleaned_symptoms.lower() for keyword in non_skin_hint_keywords)

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
            symptoms=cleaned_symptoms if cleaned_symptoms else None,
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

    try:
        if has_image:
            recommendation = await generate_recommendations_with_groq(
                image_bytes=image_bytes,
                condition=condition,
                symptoms=cleaned_symptoms if cleaned_symptoms else None,
            )
        else:
            recommendation = get_recommendations_for_disease(condition)
    except Exception:
        try:
            recommendation = get_recommendations_for_disease(condition)
        except KnowledgeBaseError:
            recommendation = {
                "drugs": [],
                "procedures": ["clinical reassessment"],
                "tests": ["targeted diagnostic evaluation"],
                "source": "knowledge_base_fallback",
            }

    drugs = recommendation.get("drugs") or []
    if isinstance(drugs, list) and drugs:
        recommendation["primary_drug"] = str(drugs[0])
        recommendation["drugs"] = [str(drugs[0])]
    else:
        recommendation["primary_drug"] = "No drug recommendation without clinician assessment"
        recommendation["drugs"] = []

    if symptom_risk in {"low", "medium", "high"}:
        risk_level = symptom_risk
    else:
        risk_level = _risk_from_confidence(confidence)

    recommendation["doctor_note"] = str(
        recommendation.get("doctor_note")
        or _build_veteran_doctor_note(condition=condition, risk_level=risk_level, symptoms=cleaned_symptoms)
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

    if has_image and not cleaned_symptoms:
        needs_symptoms = True
        follow_up_questions = [
            "I analyzed the image. What symptoms are you currently experiencing?",
            "When did these symptoms start, and are they getting worse?",
        ]
    elif cleaned_symptoms and not has_image:
        needs_image = True
        follow_up_questions = [
            "Can you upload a relevant medical image to improve confidence?",
            "If image upload is possible, share a clearer close-up from another angle.",
        ]

    return {
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
    }
