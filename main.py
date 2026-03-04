from fastapi import FastAPI
from config.settings import settings
from middleware.cors import setup_cors
from routers import api_router

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        debug=settings.debug,
        version="1.0.0",
    )

    setup_cors(app)
    app.include_router(api_router)

    @app.get("/", tags=["Root"])
    def root() -> dict:
        return {
            "status": "ok",
            "service": settings.app_name,
            "environment": settings.environment,
        }

    return app


app = create_app()
