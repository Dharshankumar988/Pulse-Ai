from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings


def setup_cors(app: FastAPI) -> None:
    origins = settings.cors_origins
    if origins == ["*"]:
        origins = ["*"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
