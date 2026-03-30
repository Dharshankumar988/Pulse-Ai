import json
from pathlib import Path


class KnowledgeBaseError(RuntimeError):
    pass


_KB_CACHE: dict | None = None


def _kb_path() -> Path:
    return Path(__file__).resolve().parent.parent / "knowledge" / "disease_knowledge_base.json"


def _load_kb() -> dict:
    global _KB_CACHE
    if _KB_CACHE is not None:
        return _KB_CACHE

    path = _kb_path()
    if not path.exists():
        raise KnowledgeBaseError(f"Knowledge base file not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, dict):
        raise KnowledgeBaseError("Knowledge base JSON must be an object")

    _KB_CACHE = data
    return data


def _normalize_disease(disease: str) -> str:
    text = (disease or "").strip().lower().replace("-", " ").replace("_", " ")
    text = " ".join(text.split())
    if "fracture" in text:
        return "fracture"
    if "tumor" in text or "neoplasm" in text or "mass" in text:
        return "tumor"
    if "kidney" in text and "stone" in text:
        return "kidney_stone"
    if "stone" in text and "renal" in text:
        return "kidney_stone"
    if "skin" in text or "dermat" in text:
        return "skin_condition"
    if "general" in text or "non specific" in text or "unknown" in text:
        return "general_non_specific_finding"
    return "general_non_specific_finding"


def get_recommendations_for_disease(disease: str, risk_level: str | None = None) -> dict:
    kb = _load_kb()
    key = _normalize_disease(disease)
    value = kb.get(key)
    if not isinstance(value, dict):
        raise KnowledgeBaseError(f"No recommendation mapping for disease key: {key}")

    first_line = value.get("first_line_drugs")
    if not isinstance(first_line, list):
        first_line = value.get("drugs", []) or []

    alternative = value.get("alternative_drugs", []) or []
    caution = value.get("avoid_or_caution", []) or []
    references = value.get("guideline_sources", []) or []

    if str(risk_level or "").lower() == "high" and len(first_line) > 1:
        selected_drugs = [str(first_line[0])]
    else:
        selected_drugs = [str(item) for item in first_line[:2]]

    return {
        "disease_key": key,
        "drugs": selected_drugs,
        "alternative_drugs": [str(item) for item in alternative[:2]],
        "safety_cautions": [str(item) for item in caution[:3]],
        "procedures": value.get("procedures", []) or [],
        "tests": value.get("tests", []) or [],
        "guideline_sources": [str(item) for item in references],
        "source": "knowledge_base",
    }
