from fastapi import FastAPI
from app.config.settings import settings
from app.routes import health

app = FastAPI(title=settings.app_name, debug=settings.debug)

app.include_router(health.router)

@app.get("/", tags=["Root"])
def root():
    return {"status": "ok", "service": settings.app_name}
