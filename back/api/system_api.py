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
            "storage": "json",
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
                "GET /api/users/{user_id}/measurements?start_date=&end_date=&page=&page_size=",
                "GET /api/users/{user_id}/measurements/stats?start_date=&end_date=",
                "POST /api/sessions",
                "DELETE /api/sessions/current",
                "GET /api/measurements?start_date=&end_date=&page=&page_size=",
                "GET /api/search?start_date=&end_date=&page=&page_size=",
                "GET /api/measurements/stats?start_date=&end_date=",
                "GET /api/stats?start_date=&end_date=",
                "POST /api/measurements",
                "GET /api/measurements/{measurement_id}",
                "PUT /api/measurements/{measurement_id}",
                "Measurement responses include BMI and health classifications",
                "DELETE /api/measurements/{measurement_id}",
            ]
        },
    )
