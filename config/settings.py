import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env from backend root (one level above config/)
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))
DEFAULT_MODELS_DIR = os.path.join(BASE_DIR, "models")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default
    return [item.strip() for item in value.split(",") if item.strip()]


def _as_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        return default


def _as_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_name: str
    environment: str
    debug: bool
    cors_origins: list[str]
    supabase_url: str
    supabase_key: str
    supabase_storage_bucket: str
    models_directory: str
    yolo_fracture_model_path: str
    yolo_tumor_model_path: str
    yolo_kidney_stone_model_path: str
    efficientnet_model_path: str
    mobilenet_model_path: str
    efficientnet_labels_path: str
    mobilenet_labels_path: str
    ml_default_confidence: float
    ml_default_top_k: int
    ml_low_confidence_threshold: float
    groq_api_key: str
    groq_model: str
    groq_vision_model: str
    groq_cache_ttl_seconds: int
    jwt_secret: str
    jwt_algorithm: str
    jwt_expiration_hours: int


settings = Settings(
    app_name=os.getenv("APP_NAME", "Pulse API"),
    environment=os.getenv("APP_ENV", "production"),
    debug=_as_bool(os.getenv("DEBUG"), default=False),
    cors_origins=_as_list(os.getenv("CORS_ORIGINS"), default=["*"]),
    supabase_url=os.getenv("SUPABASE_URL", ""),
    supabase_key=os.getenv("SUPABASE_KEY", ""),
    supabase_storage_bucket=os.getenv("SUPABASE_STORAGE_BUCKET", "medical-records"),
    models_directory=os.getenv("MODELS_DIRECTORY", DEFAULT_MODELS_DIR),
    yolo_fracture_model_path=os.getenv("YOLO_FRACTURE_MODEL_PATH", os.path.join(DEFAULT_MODELS_DIR, "fracture_model.pt")),
    yolo_tumor_model_path=os.getenv("YOLO_TUMOR_MODEL_PATH", os.path.join(DEFAULT_MODELS_DIR, "brain_model.pt")),
    yolo_kidney_stone_model_path=os.getenv("YOLO_KIDNEY_STONE_MODEL_PATH", os.path.join(DEFAULT_MODELS_DIR, "kidney_model.pt")),
    efficientnet_model_path=os.getenv("EFFICIENTNET_MODEL_PATH", os.path.join(DEFAULT_MODELS_DIR, "skin_model.pt")),
    mobilenet_model_path=os.getenv("MOBILENET_MODEL_PATH", ""),
    efficientnet_labels_path=os.getenv("EFFICIENTNET_LABELS_PATH", ""),
    mobilenet_labels_path=os.getenv("MOBILENET_LABELS_PATH", ""),
    ml_default_confidence=_as_float(os.getenv("ML_DEFAULT_CONFIDENCE"), default=0.25),
    ml_default_top_k=_as_int(os.getenv("ML_DEFAULT_TOP_K"), default=3),
    ml_low_confidence_threshold=_as_float(os.getenv("ML_LOW_CONFIDENCE_THRESHOLD"), default=0.7),
    groq_api_key=os.getenv("GROQ_API_KEY", ""),
    groq_model=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
    groq_vision_model=os.getenv("GROQ_VISION_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
    groq_cache_ttl_seconds=_as_int(os.getenv("GROQ_CACHE_TTL_SECONDS"), default=600),
    jwt_secret=os.getenv("JWT_SECRET", "pulse-dev-secret-change-in-production"),
    jwt_algorithm=os.getenv("JWT_ALGORITHM", "HS256"),
    jwt_expiration_hours=_as_int(os.getenv("JWT_EXPIRATION_HOURS"), default=24),
)
