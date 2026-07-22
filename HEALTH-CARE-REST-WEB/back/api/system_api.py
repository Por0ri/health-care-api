from flask import Blueprint

from .responses import success_response

system_api = Blueprint("system_api", __name__)


@system_api.get("/api/health")
def health_check():
    return success_response(
        "서버가 정상적으로 실행 중입니다.",
        {
            "service": "health-care-rest-api",
            "status": "ok",
        },
    )


@system_api.get("/api")
def api_index():
    return success_response(
        "Health Care REST API 목록입니다.",
        {
            "endpoints": [
                "POST /api/users",
                "GET /api/users",
                "GET /api/users/{user_id}",
                "GET /api/users/{user_id}/measurements",
                "POST /api/sessions",
                "DELETE /api/sessions/current",
                "GET /api/measurements",
                "POST /api/measurements",
                "GET /api/measurements/{measurement_id}",
            ]
        },
    )
