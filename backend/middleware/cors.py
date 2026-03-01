from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings

# Starlette ≥0.40 silently drops the Access-Control-Allow-Origin header
# when allow_origins=["*"] AND allow_credentials=True (forbidden by spec).
# Fix: when the user hasn't set explicit origins, we list common front-end
# origins so the middleware can reflect the exact Origin header back.
_FALLBACK_ORIGINS = [
    "https://pulse-cs050.vercel.app",
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]


def setup_cors(app: FastAPI) -> None:
    origins = settings.cors_origins
    # Replace wildcard with explicit list so credentials + origin works
    if origins == ["*"]:
        origins = _FALLBACK_ORIGINS

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
