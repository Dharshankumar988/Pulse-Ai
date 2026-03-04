from config.settings import settings


def get_health_status() -> dict:
    return {
        "status": "healthy",
        "service": settings.app_name,
        "environment": settings.environment,
    }
