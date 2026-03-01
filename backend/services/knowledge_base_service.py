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


def get_recommendations_for_disease(disease: str) -> dict:
    kb = _load_kb()
    key = _normalize_disease(disease)
    value = kb.get(key)
    if not isinstance(value, dict):
        raise KnowledgeBaseError(f"No recommendation mapping for disease key: {key}")

    return {
        "disease_key": key,
        "drugs": value.get("drugs", []) or [],
        "procedures": value.get("procedures", []) or [],
        "tests": value.get("tests", []) or [],
        "source": "knowledge_base",
    }
