from flask import Blueprint, g, request

from database import (
    create_measurement,
    delete_measurement,
    get_measurement,
    get_measurement_statistics,
    search_user_measurements,
    update_measurement,
)
from .auth import require_role
from .responses import error_response, success_response

measurement_api = Blueprint("measurement_api", __name__)


def _measurement_query_arguments() -> dict:
    return {
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
        "page": request.args.get("page", 1),
        "page_size": request.args.get("page_size", 5),
    }


def _statistics_query_arguments() -> dict:
    return {
        "start_date": request.args.get("start_date"),
        "end_date": request.args.get("end_date"),
    }


def _current_user_search_response():
    result = search_user_measurements(
        g.session["account_id"],
        **_measurement_query_arguments(),
    )

    return success_response(
        "날짜 범위에 해당하는 측정 기록을 조회했습니다.",
        result,
    )


@measurement_api.get("/api/measurements")
@require_role("user")
def list_measurement_resources():
    return _current_user_search_response()


# 과제 명세의 GET /search에 대응하는 별칭이다.
@measurement_api.get("/api/search")
@require_role("user")
def search_measurement_resources():
    return _current_user_search_response()


@measurement_api.get("/api/measurements/stats")
@require_role("user")
def get_measurement_statistics_resource():
    statistics = get_measurement_statistics(
        g.session["account_id"],
        **_statistics_query_arguments(),
    )

    return success_response(
        "측정 기록 평균을 계산했습니다.",
        {"statistics": statistics},
    )


# 과제 명세의 GET /stats에 대응하는 별칭이다.
@measurement_api.get("/api/stats")
@require_role("user")
def get_statistics_alias_resource():
    statistics = get_measurement_statistics(
        g.session["account_id"],
        **_statistics_query_arguments(),
    )

    return success_response(
        "측정 기록 평균을 계산했습니다.",
        {"statistics": statistics},
    )


@measurement_api.post("/api/measurements")
@require_role("user")
def create_measurement_resource():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "JSON 요청 본문이 필요합니다.",
            status=400,
            error_type="request",
        )

    user_id = g.session["account_id"]
    measurement = create_measurement(user_id, data)
    statistics = get_measurement_statistics(user_id)

    return success_response(
        "건강 수치 계산 후 측정 정보가 저장되었습니다.",
        {
            "measurement": measurement,
            "warnings": measurement.get("warnings", []),
            "statistics": statistics,
        },
        status=201,
    )


@measurement_api.get("/api/measurements/<int:measurement_id>")
@require_role()
def get_measurement_resource(measurement_id: int):
    measurement = get_measurement(measurement_id)

    if measurement is None:
        return error_response(
            "측정 정보를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    if (
        g.session["role"] == "user"
        and measurement["user_id"] != g.session["account_id"]
    ):
        return error_response(
            "다른 사용자의 측정 정보는 조회할 수 없습니다.",
            status=403,
            error_type="permission",
        )

    return success_response(
        "측정 정보를 조회했습니다.",
        {"measurement": measurement},
    )


@measurement_api.put("/api/measurements/<int:measurement_id>")
@require_role("user")
def update_measurement_resource(measurement_id: int):
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return error_response(
            "JSON 요청 본문이 필요합니다.",
            status=400,
            error_type="request",
        )

    existing = get_measurement(measurement_id)

    if existing is None:
        return error_response(
            "수정할 측정 정보를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    user_id = g.session["account_id"]

    if existing["user_id"] != user_id:
        return error_response(
            "다른 사용자의 측정 정보는 수정할 수 없습니다.",
            status=403,
            error_type="permission",
        )

    measurement = update_measurement(
        measurement_id,
        user_id,
        data,
    )

    if measurement is None:
        return error_response(
            "측정 정보 수정에 실패했습니다.",
            status=409,
            error_type="update_failed",
        )

    statistics = get_measurement_statistics(user_id)

    return success_response(
        "측정 기록 전체가 수정되었습니다.",
        {
            "measurement": measurement,
            "warnings": measurement.get("warnings", []),
            "statistics": statistics,
        },
    )


@measurement_api.delete("/api/measurements/<int:measurement_id>")
@require_role()
def delete_measurement_resource(measurement_id: int):
    measurement = get_measurement(measurement_id)

    if measurement is None:
        return error_response(
            "삭제할 측정 정보를 찾을 수 없습니다.",
            status=404,
            error_type="not_found",
        )

    role = g.session["role"]
    account_id = g.session["account_id"]

    if role == "user" and measurement["user_id"] != account_id:
        return error_response(
            "다른 사용자의 측정 정보는 삭제할 수 없습니다.",
            status=403,
            error_type="permission",
        )

    if not delete_measurement(measurement_id):
        return error_response(
            "측정 정보 삭제에 실패했습니다.",
            status=409,
            error_type="delete_failed",
        )

    statistics = get_measurement_statistics(
        measurement["user_id"]
    )

    return success_response(
        "측정 기록이 삭제되었습니다.",
        {
            "measurement_id": measurement_id,
            "user_id": measurement["user_id"],
            "deleted_by": {
                "role": role,
                "account_id": account_id,
            },
            "statistics": statistics,
        },
    )
